"""Integrated LAN lobby and async controller. All mutations run on the host."""
import copy,secrets,threading,uuid,datetime
from pathlib import Path
from PySide6.QtCore import QObject,Signal,QTimer
from PySide6.QtWidgets import QDialog,QVBoxLayout,QComboBox,QLineEdit,QMessageBox,QApplication
import app as ui
from game import Game,money
from lan_discovery import scan
from lan import Server,rpc,addresses,save_credentials,load_credentials

class Connection(QObject):
    response=Signal(object);failure=Signal(str)
    def __init__(self,credentials,path,latest_path=None):
        super().__init__();self.c=credentials;self.path=Path(path);self.latest_path=latest_path
        self.busy=False;self.online=False;self.view=None;self.closed=False
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(1000)
    def persist(self,latest=False):
        save_credentials(self.path,self.c)
        if latest and self.latest_path:save_credentials(self.latest_path,self.c)
    def send(self,op,**args):
        if self.c.get('pending') or self.closed:return False
        self.c['pending']=dict(op=op,request_id=uuid.uuid4().hex,**args)
        try:self.persist(latest=self.view is not None)
        except OSError:
            self.c.pop('pending',None);self.failure.emit('Kunne ikke gemme handlingen lokalt. Ingen handling er sendt.');return False
        self.tick();return True
    def tick(self):
        if self.busy or self.closed:return
        self.busy=True
        message=copy.deepcopy(dict(self.c.get('pending') or {'op':'poll'},token=self.c['token']))
        invite=self.c['invite']
        def work():
            try:
                result=rpc(invite,message)
                if not self.closed:self.response.emit((message,result))
            except Exception as e:
                if not self.closed:self.failure.emit(str(e))
            finally:
                if self.closed:self.busy=False
        threading.Thread(target=work,daemon=True).start()
    def stop(self):
        self.closed=True;self.timer.stop()

class LanWindow(ui.Window):
    def __init__(self,controller,lobby):
        self.controller=controller;self.lobby=lobby
        g=Game();g.s=controller.view['state']
        super().__init__(g)
        self.statusBar().showMessage('LAN · '+controller.view['name']+' · Eget dagtempo')
    def new(self,*a):QMessageBox.information(self,'LAN','Afslut denne session og genstart programmet for at oprette et nyt spil.')
    def autosave(self):pass
    def present_day_events(self):
        if self.controller.c.get('pending') or not self.controller.online:return
        super().present_day_events()
    def act(self,action,**args):
        c=self.controller
        if c.c.get('pending') or not c.online:return
        if not c.send('command',revision=c.view['revision'],action=action,args=args):return
        self.main.setEnabled(False)
        if self.panel:self.panel.setEnabled(False)
    def scores(self):
        v=self.controller.view
        self.bl.addWidget(ui.label('Slutresultat' if v['complete'] else 'Foreløbig LAN-stilling','section'))
        self.bl.addWidget(ui.label('Score = bank + aktivernes salgsværdi − gæld. Spillerne har individuelt dagtempo.','muted'))
        players=sorted(v['players'],key=lambda p:(not p.get('dnf',False),p['score']),reverse=True);rows=[];rank=0;previous=None
        for i,p in enumerate(players):
            if p['score']!=previous:rank=i+1
            previous=p['score']
            rows.append(['—' if p.get('dnf') else rank,p['name'],str(p['day'])+'/'+str(v['days']),money(p['bank']),money(p['score']),'Opgivet af vært' if p.get('dnf') else ('Afsluttet' if p['finished'] else ('Aktiv' if p['online'] else 'Offline'))])
        self.bl.addWidget(ui.table(['#','Spiller','Dag','Bank','Score','Status'],rows,300))
        if self.lobby.server:
            for p in v['players']:
                if not p['finished'] and p['id']!=v['me']:
                    self.bl.addWidget(ui.button('Markér '+p['name']+' som opgivet…',lambda p=p:self.lobby.retire(p)))
        if not self.g.s['finished']:self.bl.addWidget(ui.button('Afslut mit spil',self.finish))
    def closeEvent(self,event):
        text='Forlad midlertidigt? Din spiller gemmes og kan genforbindes.'
        if self.lobby.server:text='Luk værtsprogrammet? Alle mister forbindelsen, men sessionen er gemt og kan genoptages.'
        if QMessageBox.question(self,'Forlad LAN',text)!=QMessageBox.StandardButton.Yes:event.ignore();return
        self.controller.stop()
        if self.lobby.server:self.lobby.server.close()
        self.lobby.close();event.accept()

class Lobby(QDialog):
    discovered=Signal(object)
    def __init__(self):
        super().__init__();self.setWindowTitle('Dope Wars — BFT LAN');self.resize(700,590)
        self.layout=QVBoxLayout(self);self.server=None;self.controller=None;self.window=None
        self.path=ui.DATA/'LAN'/'client.dpapi'
        self.browsing=False;self.scan_busy=False
        self.discovered.connect(self.found)
        self.search_timer=QTimer(self);self.search_timer.timeout.connect(self.search);self.search_timer.start(3000)
        self.setup()
    def clear(self):
        self.browsing=False
        while self.layout.count():
            w=self.layout.takeAt(0).widget()
            if w:w.hide();w.deleteLater()
    def setup(self):
        self.clear();self.layout.addWidget(ui.label('LAN · Opret eller deltag','title'))
        self.layout.addWidget(ui.label('Samme EXE på alle pc’er. Alle spiller i eget tempo. Startby: Høje på Fyn.'))
        self.name=QLineEdit();self.name.setPlaceholderText('Dit spillernavn');self.name.setMaxLength(24);self.layout.addWidget(self.name)
        self.days=QComboBox()
        for d in (31,90,180,365):self.days.addItem(f'{d} dage',d)
        self.layout.addWidget(self.days)
        self.layout.addWidget(ui.button('Opret ny LAN-lobby',self.host,'primary'))
        self.layout.addWidget(ui.label('Spil på dit lokalnet','section'))
        self.games=QComboBox();self.layout.addWidget(self.games)
        self.search_note=ui.label('Søger efter åbne lobbyer…','muted');self.layout.addWidget(self.search_note)
        self.join_found=ui.button('Deltag i valgt spil',self.join_discovered,'primary');self.join_found.setEnabled(False);self.layout.addWidget(self.join_found)
        self.games.currentIndexChanged.connect(lambda:self.join_found.setEnabled(bool(self.games.currentData()) and self.games.currentData()['players']<8))
        self.layout.addWidget(ui.button('Søg igen',self.search))
        self.invite=QLineEdit();self.invite.setPlaceholderText('Reserve: indsæt invitation, hvis spillet ikke findes');self.invite.hide()
        self.manual=ui.button('Deltag via invitation',self.join);self.manual.hide()
        self.layout.addWidget(ui.button('Kan du ikke finde spillet? Vis invitation',lambda:(self.invite.show(),self.manual.show())))
        self.layout.addWidget(self.invite);self.layout.addWidget(self.manual)
        self.browsing=True;QTimer.singleShot(0,self.search)
        self.saved=QComboBox()
        for path,c in self.saved_connections():
            title=c.get('session_name',c.get('name','Gemt spil'))+' · '+('Vært' if c.get('directory') else 'Deltager')
            if c.get('complete'):title+=' · afsluttet'
            self.saved.addItem(title,str(path))
        if self.saved.count():
            self.layout.addWidget(ui.label('Gemte LAN-sessioner','section'))
            self.layout.addWidget(self.saved)
            self.layout.addWidget(ui.button('Genoptag valgt session',self.resume))
        else:self.saved.hide()
        self.layout.addWidget(ui.label('Værten skal tillade appen på privat Windows-netværk. Alle skal være på samme lokalnet; isolerede gæstenet understøttes ikke.','muted'))
        self.layout.addWidget(ui.label('Kontanter og varer er private. Den fælles stilling viser kun lovlig nettoformue.','muted'))
    def saved_connections(self):
        folder=self.path.parent/(self.path.stem+'-connections')
        paths=([self.path] if self.path.exists() else [])+sorted(folder.glob('*.dpapi'),key=lambda p:p.stat().st_mtime,reverse=True)
        records=[];tokens=set()
        for path in paths:
            try:
                c=load_credentials(path)
                if c.get('token') not in tokens and ('session' in c or path==self.path):
                    records.append((path,c));tokens.add(c['token'])
            except Exception:continue
        return records

    def search(self):
        if not self.browsing or self.scan_busy:return
        self.scan_busy=True
        def work():
            try:result=scan()
            except Exception:result=[]
            self.discovered.emit(result)
        threading.Thread(target=work,daemon=True).start()
    def found(self,games):
        self.scan_busy=False
        if not self.browsing:return
        selected=self.games.currentData();sid=selected['session'] if selected else None
        self.games.blockSignals(True);self.games.clear()
        for g in games:self.games.addItem(f"{g['name']} · {g['players']}/8 spillere · {g['days']} dage",g)
        for i,g in enumerate(games):
            if g['session']==sid:self.games.setCurrentIndex(i)
        self.games.blockSignals(False)
        selected=self.games.currentData();self.join_found.setEnabled(bool(selected) and selected['players']<8)
        self.search_note.setText('Vælg et spil og tryk Deltag.' if games else 'Ingen åbne spil fundet endnu. Værten skal oprette en lobby. Der søges automatisk igen.')
    def join_discovered(self):
        if not self.name.text().strip():self.name.setFocus();return
        game=self.games.currentData()
        if game:self.invite.setText(game['invite']);self.join()
    def host(self):
        if not self.name.text().strip():return
        try:
            directory=ui.DATA/'LAN'/uuid.uuid4().hex
            self.server=Server(directory,self.days.currentData(),name=self.name.text().strip()+"s lobby")
            invitation=self.server.invite('127.0.0.1')
            self.begin(dict(invite=invitation,token=secrets.token_hex(32),name=self.name.text().strip(),directory=str(directory),pending=dict(op='join',owner=self.server.session.s['owner'],name=self.name.text().strip())))
        except Exception as e:QMessageBox.warning(self,'Kunne ikke være vært',str(e))
    def join(self):
        if not self.name.text().strip():return
        self.begin(dict(invite=self.invite.text().strip(),token=secrets.token_hex(32),name=self.name.text().strip(),pending=dict(op='join',name=self.name.text().strip())))
    def resume(self):
        try:
            c=load_credentials(Path(self.saved.currentData()) if self.saved.count() else self.path)
            if c.get('directory'):
                port=int(c['invite'].split('|')[1]);self.server=Server(c['directory'],port=port)
                c['invite']=self.server.invite('127.0.0.1')
            elif self.invite.text().strip():
                if c['invite'].split('|')[2]!=self.invite.text().strip().split('|')[2]:raise ValueError('Den nye invitation kommer fra en anden vært/session.')
                c['invite']=self.invite.text().strip()
            if not c.get('pending'):c['pending']=dict(op='join',name=c['name'])
            self.begin(c)
        except Exception as e:QMessageBox.warning(self,'Kunne ikke genoptage',str(e))
    def begin(self,c):
        try:
            parts=c['invite'].split('|')
            if len(parts)!=4 or not 1<=int(parts[1])<=65535 or len(parts[2])!=64:raise ValueError('Indsæt hele invitationen fra værten.')
            folder=self.path.parent/(self.path.stem+'-connections')
            folder.mkdir(parents=True,exist_ok=True)
            # Archive the previous session BEFORE attempting a different join.
            for oldpath,old in self.saved_connections():
                dest=folder/(old['token']+'.dpapi')
                if not dest.exists():save_credentials(dest,old)
            path=folder/(c['token']+'.dpapi');save_credentials(path,c)
            if self.controller:self.controller.stop()
            self.controller=Connection(c,path,self.path)
            connection=self.controller
            connection.response.connect(lambda result,c=connection:self.received(c,result))
            connection.failure.connect(lambda error,c=connection:self.failed(c,error))
            self.clear();self.layout.addWidget(ui.label('Forbinder til LAN…','title'));self.controller.tick()
        except Exception as e:QMessageBox.warning(self,'Forbindelse',str(e))
    def failed(self,c,error):
        if c is not self.controller or c.closed:return
        c.busy=False;c.online=False;c.timer.setInterval(min(10000,c.timer.interval()*2))
        text='Genforbinder… Kontrollér at værten kører. '+error[:160]
        if self.window:
            self.window.main.setEnabled(False)
            if self.window.panel:self.window.panel.setEnabled(False)
            self.window.statusBar().showMessage(text)
        else:
            self.clear();self.layout.addWidget(ui.label(text));self.layout.addWidget(ui.button('Tilbage',self.cancel))
    def retire(self,p):
        if QMessageBox.question(self,'Fjern deltager',p['name']+' fjernes fra lobbyen eller markeres som opgivet uden vinderplacering. Fortsæt?')==QMessageBox.StandardButton.Yes:
            self.controller.send('retire',target=p['id'])
    def leave_lobby(self):
        if self.server:self.cancel()
        elif self.controller and self.controller.online:self.controller.send('leave')
        else:self.cancel()
    def cancel(self):
        if self.controller:self.controller.stop()
        self.controller=None
        if self.server:self.server.close();self.server=None
        self.setup()
    def received(self,c,envelope):
        if c is not self.controller or c.closed:return
        sent,response=envelope
        c.busy=False;c.online=True;c.timer.setInterval(1000)
        pending=c.c.get('pending')
        if pending and all(sent.get(k)==v for k,v in pending.items()):
            c.c.pop('pending',None)
            try:c.persist(latest=c.view is not None)
            except OSError:self.failed(c,'Kunne ikke gemme forbindelsen lokalt.');return
        if c.c.get('pending'):QTimer.singleShot(0,c.tick)
        if not response.get('ok'):
            QMessageBox.information(self,'LAN',response.get('error','Forbindelsesfejl'))
            if c.view is None:self.cancel()
            elif sent['op'] in ('poll','join'):
                c.stop()
                if self.window:
                    self.window.main.setEnabled(False)
                    if self.window.panel:self.window.panel.setEnabled(False)
                    self.window.statusBar().showMessage('Forbindelsen er afvist. Luk og genoptag sessionen.')
            else:c.tick()
            return
        v=response['view']
        if v.get('left'):self.cancel();return
        old=c.view;c.view=v
        metadata=dict(session=v['session'],session_name=v['name'],days=v['days'],complete=v['complete'])
        if pending or any(c.c.get(k)!=value for k,value in metadata.items()):
            c.c.update(metadata);c.c['updated']=datetime.datetime.now().isoformat()
            try:c.persist(latest=True)
            except OSError:self.failed(c,'Kunne ikke gemme forbindelsen.');return
        if v['started']:
            if not self.window:self.window=LanWindow(c,self);self.window.show();self.hide();changed=True
            else:changed=old is None or old['revision']!=v['revision']
            w=self.window
            if changed:
                w.g.s=v['state'];w.last_notice=w.g.s['log'][0];w.render()
                if w.panel and w.panel.isVisible():w.refresh_panel()
            elif old and old['players']!=v['players'] and w.panel and w.panel.isVisible() and w.panel_page==6:w.refresh_panel()
            w.main.setEnabled(not c.c.get('pending'))
            if w.panel:w.panel.setEnabled(not c.c.get('pending'))
            w.statusBar().showMessage('LAN · '+v['name']+' · Forbundet · '+('Alle er færdige' if v['complete'] else 'Eget dagtempo'))
            if not c.c.get('pending'):
                QTimer.singleShot(0,w.present_day_events)
            return
        if old==v:return
        self.clear();self.layout.addWidget(ui.label('Lobby · '+v['name'],'title'))
        self.layout.addWidget(ui.label(f"{v['days']} dage · Høje på Fyn · Eget dagtempo · {len(v['players'])}/8 spillere"))
        if self.server:
            address=QComboBox();address.addItems(addresses())
            field=QLineEdit(self.server.invite(address.currentText()));field.setReadOnly(True)
            address.currentTextChanged.connect(lambda host:field.setText(self.server.invite(host)))
            self.layout.addWidget(ui.label('Dine venner finder lobbyen automatisk under Spil på dit lokalnet.' if self.server.discovery else 'Automatisk søgning er ikke tilgængelig. Brug invitationen nedenfor.'))
            address.hide();field.hide()
            self.layout.addWidget(ui.button('Vis reserveinvitation',lambda:(address.show(),field.show())))
            self.layout.addWidget(address);self.layout.addWidget(field)
            self.layout.addWidget(ui.button('Kopiér invitation',lambda:QApplication.clipboard().setText(field.text())))
        self.layout.addWidget(ui.table(['Spiller','Rolle','Klar','Forbindelse'],[[p['name'],'Vært' if p['owner'] else 'Deltager','Ja' if p['ready'] else 'Nej','Online' if p['online'] else 'Offline'] for p in v['players']],220))
        me=next(p for p in v['players'] if p['id']==v['me'])
        self.layout.addWidget(ui.button('Fortryd klar' if me['ready'] else 'Jeg er klar',lambda:c.send('ready')))
        if me['owner']:
            b=ui.button('Start spillet',lambda:c.send('start'),'primary');b.setEnabled(len(v['players'])>=2 and all(p['ready'] and p['online'] for p in v['players']));self.layout.addWidget(b)
        if me['owner']:
            for p in v['players']:
                if p['id']!=v['me']:self.layout.addWidget(ui.button('Fjern '+p['name']+'…',lambda p=p:self.retire(p)))
        self.layout.addWidget(ui.button('Forlad lobby',self.leave_lobby))
    def closeEvent(self,event):
        self.browsing=False;self.search_timer.stop()
        if self.controller:self.controller.stop()
        if self.server:self.server.close()
        event.accept()

def choose_mode():
    d=QDialog();d.setWindowTitle(ui.APP_NAME);l=QVBoxLayout(d);d.resize(420,240)
    l.setContentsMargins(20,18,20,18);l.setSpacing(10)
    l.addWidget(ui.row(ui.logo_widget(58),ui.label('Dope Wars\nBFT edition','title'),1))
    l.addWidget(ui.label('Spil alene eller med vennerne på lokalnettet.','muted'))
    result=['single']
    def pick(mode):result[0]=mode;d.accept()
    l.addWidget(ui.button('Singleplayer',lambda:pick('single')));l.addWidget(ui.button('LAN · vært eller deltager',lambda:pick('lan'),'primary'))
    return result[0] if d.exec()==QDialog.DialogCode.Accepted else None
