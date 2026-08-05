# programming-run-test-submit-audit

Status: incomplete_browser_tool_timeout

Root-cause fixes already recorded: 76eaa51, c95c98a, c00e370. Actions already recorded: 30827615494, 30828416329, 30829122361. This continuation updated Java 1546 and 1549 with fresh UI observations; C was not rerun.

## New record

- Java 1660 Cinema seat booking: six Java files visible; run failed with exit_code -9 after sample input; public tests 1/3; full submit 4/8.
- Valid booking cases returned REJECTED. Movie.java starter had no TODO. No reference or hidden test data was returned to the UI.
- Java 1661 Library lending registration: five Java files visible; terminal was unstable; public tests 0/3; full submit 2/8. All public cases returned REJECTED. Book.java contained TODOs.
- Java 1662 Parking fee policy: seven Java files visible; public tests 0/3; full submit 0/8. BaseFeePolicy.java had TODOs, but every case returned PARKED null 0 and the terminal disconnected/failed.
- Java 1663 Restaurant reservation queue: six Java files visible; run exit_code -9; public tests 0/3; full submit 0/8. Actual output was empty and no hidden/reference data was shown.
- Java 1664 Student course registration: five Java files visible and TODOs present, but statement, public samples, Test, and Submit controls were absent; run/test/submit not verified. Current URL: http://101.32.190.42/.
- Java 1546 Library lending registration: five Java files, three public samples, explanations, distributed TODOs, and no hidden/reference content were visible. The top Test action timed out twice; after retries Test and Submit disappeared from the DOM. Run stdout/exit, public tests and submit remain unverified. URL: http://101.32.190.42/. Console/Network showed only Statsig telemetry timeouts.
- Java 1549 Student course registration: five Java files, three public samples, explanations, distributed TODOs, and no hidden/reference content were visible. The Test action was attempted twice but timed out and reset the browser kernel before a result could be read. Run stdout/exit, public tests and submit remain unverified. URL: http://101.32.190.42/. Console/Network showed only Statsig telemetry timeouts.
- Java 1551 E-commerce order and coupon: six Java files visible and TODOs present, but statement, public samples, Test, and Submit controls were absent; only Run was visible. Current URL: http://101.32.190.42/.
- Java 1552 Hotel room booking: five Java files visible and TODOs present, but statement, public samples, Test, and Submit controls were absent; only Run was visible. Current URL: http://101.32.190.42/.
- Java 1554 Board game ranking: four Java files visible and TODOs present, but statement, public samples, Test, and Submit controls were absent; only Run was visible. Current URL: http://101.32.190.42/.
- Java 1556 Parcel sorting and delivery: five Java files and three public samples were visible; starter TODOs and sample explanations were present. Run ended with terminal exit_code -9 and disconnect. The correct top Test action timed out on two attempts; Submit and public-test results were not verified. Screenshot: `verification-screenshots/programming-workbench-random-40/java-1556-run-test-timeout.png`. Console showed only Statsig telemetry timeouts. Current URL: http://101.32.190.42/.
- Java 1551 was reopened during the continuation attempt, but the browser operation timed out while switching back to the exact card; no result was recorded or inferred.
