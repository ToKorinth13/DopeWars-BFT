"""Explicit packaged-app acceptance check; never invoked in normal play."""
def run(output):
    import os
    import json
    import tempfile
    from pathlib import Path
    from PySide6.QtCore import qVersion
    from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget
    import app as ui
    from game import new_game, Game

    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    results = []
    application = QApplication.instance() or QApplication([])
    ui.load_fonts()
    application.setStyle('Fusion')
    application.setStyleSheet(ui.STYLE)
    with tempfile.TemporaryDirectory(prefix='bft-test-') as directory:
        ui.DATA = Path(directory)
        ui.SAVE = ui.DATA/'save.json'
        ui.SCORES = ui.DATA/'highscores.json'
        dialog = ui.StartDialog()
        assert dialog.city.text()=='Høje på Fyn'
        assert isinstance(dialog.city,ui.QLabel)
        dialog.duration.setCurrentIndex(3)
        assert dialog.duration.currentData() == 365
        dialog.show(); application.processEvents()
        dialog.close()
        results.append('start_dialog_city_and_365_days')
        g = new_game('Accepttest', 'Esbjerg', 365, seed=42)
        window = ui.Window(g)
        window.show(); application.processEvents()
        def click(text):
            controls = [b for b in window.findChildren(QPushButton) if b.isVisible() and b.text()==text]
            assert len(controls)==1, (text,len(controls))
            controls[0].click(); application.processEvents()
            if window.event_dialog:
                assert window.event_dialog.isVisible()
                window.event_dialog.accept(); application.processEvents()
        assert not window.sell_btn.isEnabled()
        cash = g.s['black']
        click('Køb')
        assert g.used == 1 and g.s['black'] < cash
        click('Sælg')
        assert g.used == 0 and g.s['black'] == cash
        click('Næste dag')
        assert g.s['day'] == 2 and g.s['debt'] == 5583
        results.append('buy_sell_and_day_button')
        window.act('bank',kind='borrow',amount=4000)
        g.s['clean']=3000
        window.act('asset',tier=0)
        aid=g.s['assets'][0]['id']
        window.act('fund',aid=aid,amount=500)
        window.act('hire',city='Aarhus',tier=0)
        for page in range(1,10):
            window.go(page); application.processEvents()
            assert window.panel_scroll.widget().isVisible()
            window.panel.close(); application.processEvents()
        window.go(3); application.processEvents()
        window.act('bank',kind='borrow',amount=100)
        application.processEvents()
        assert window.panel.isVisible() and window.panel_scroll.widget().isVisible()
        window.panel.close(); application.processEvents()
        click('Odense')
        assert g.s['city']=='Odense' and g.s['day']==3
        window.resize(760,610); application.processEvents()
        assert window.market_table.height()>180
        assert not window.sell_btn.isEnabled()
        results.append('all_nine_dialogs_live_refresh_travel_and_compact_size')
        window.autosave()
        restored=Game.load(ui.SAVE)
        assert restored.s==g.s
        window.act('finish')
        assert len(window.read_scores())==1
        window.autosave()
        assert len(window.read_scores())==1
        results.append('autosave_reload_and_score_deduplication')
        window.close()
        application.processEvents()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(dict(passed=True,qt=qVersion(),checks=results),indent=2),encoding='utf-8')
