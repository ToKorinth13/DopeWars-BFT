def run(output):
    import io,json,unittest
    from test_lan import LanTests
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromTestCase(LanTests))
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,details=stream.getvalue()),indent=2),encoding='utf-8')
    if not result.wasSuccessful():raise SystemExit(1)
