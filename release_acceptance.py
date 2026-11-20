"""Explicit release checks, isolated from the player's saved data.

Invoked only with --release-self-test <json-output>. Uses local TLS sockets.
"""
def run(output):
    import io,json,os,time,unittest
    os.environ['QT_QPA_PLATFORM']='offscreen'
    import test_game,test_lan,test_release,test_ui,test_events
    from game import VERSION,RULESET
    stream=io.StringIO();started=time.monotonic()
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m)
                            for m in (test_game,test_lan,test_release,test_ui,test_events))
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    report=dict(version=VERSION,ruleset=RULESET,passed=result.wasSuccessful(),
                tests=result.testsRun,seconds=round(time.monotonic()-started,2),
                errors=len(result.errors),failures=len(result.failures),
                details=stream.getvalue(),scope='Engine, Qt UI and real TLS on one Windows PC; no physical multi-PC/firewall test.')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    if not result.wasSuccessful():raise SystemExit(1)
