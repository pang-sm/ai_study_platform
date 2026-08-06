# java-multifile-scroll-audit

Status: incomplete_browser_tool_timeout

## Completed in this continuation

| exercise_id | file_count | entry | last_file_reachable | starter_todo | run | public | submit | status |
|---:|---:|---|---|---|---|---|---|---|
|1660|6|Main.java|yes|no|exit -9|1/3|4/8|failed|
|1661|5|Main.java|yes|yes|unstable|0/3|2/8|failed|
|1662|7|Main.java|yes|yes|unstable|0/3|0/8|failed|
|1663|6|Main.java|yes|no|exit -9|0/3|0/8|failed|
|1664|5|Main.java|yes|yes|not verified|n/a|n/a|failed|
|1546|5|Main.java|yes|yes|not captured|n/a|n/a|failed: Test timeout twice; controls disappeared|
|1549|5|Main.java|yes|yes|not captured|n/a|n/a|failed: Test timeout twice; browser reset|
|1551|6|Main.java|yes|yes|not verified|n/a|n/a|failed|
|1552|5|Main.java|yes|yes|not verified|n/a|n/a|failed|
|1554|4|Main.java|yes|yes|not verified|n/a|n/a|failed|
|1556|5|Main.java|yes|yes|exit -9|not verified|not verified|failed|

Files: BookingService.java, Customer.java, Main.java, Movie.java, Screening.java, Seat.java.

Observed defect: Movie.java starter is a complete implementation with no TODO. The valid booking cases returned REJECTED. The runtime terminal disconnected after sample input and reported exit_code -9. No reference solution or hidden test content was visible.

1662 displayed seven files. BaseFeePolicy.java was checked and had a TODO framework; the previously reported similarity issue was not visible in this starter. All public and full tests returned PARKED null 0. No reference or hidden test content was visible.

1663 displayed six files, including ReservationStatus.java. After sample input the terminal reported exit_code -9; public and full tests returned empty actual output. No reference or hidden test content was visible.

1664 displayed Course.java, Enrollment.java, Main.java, Registrar.java, and Student.java, with TODOs in Course.java. The Workbench omitted the statement, public samples, Test button, and Submit button; only Run was visible. Current URL: http://101.32.190.42/.

1546 displayed five files and Book.java TODOs; three public samples and explanations were visible and hidden/reference content was absent. Test timed out twice; after retries Test and Submit disappeared from the DOM. Run/public/submit remain unverified. Current URL: http://101.32.190.42/.

1549 displayed five files and Course.java TODOs; three public samples and explanations were visible and hidden/reference content was absent. Test timed out twice and the browser kernel reset before a result could be read. Run/public/submit remain unverified. Current URL: http://101.32.190.42/.

1551 displayed six files and Product.java TODOs, but the statement, public samples, Test button, and Submit button were absent. Only Run was visible. Current URL: http://101.32.190.42/.

1552 displayed five files and Room.java TODOs, but the statement, public samples, Test button, and Submit button were absent. Only Run was visible. Current URL: http://101.32.190.42/.

1554 displayed four files and Player.java TODOs, but the statement, public samples, Test button, and Submit button were absent. Only Run was visible. Current URL: http://101.32.190.42/.

1556 displayed DeliveryStatus.java, DispatchCenter.java, Main.java, Parcel.java, and Route.java. The file list was independently visible, the last file was reachable, and the starter contained TODOs. Three public samples and explanations were visible. Run ended with a terminal disconnect and exit_code -9. The top public Test action timed out on two attempts after the result pane was active; Submit and public-test execution were not verified. Screenshot: `verification-screenshots/programming-workbench-random-40/java-1556-run-test-timeout.png`. URL: http://101.32.190.42/.

Pending current random sample: 1549, 1551, 1552, 1554. 1546 remains incomplete for run/test/submit despite its UI content now being verified. Previous specialized 12-exercise audit is not substituted for this browser sample.

## Continuation 2026-08-05

Java 1809 is a single-file Java exercise and therefore does not change the multi-file scroll count. Its official submit passed 8/8 after the trailing-space correction; no hidden/reference content was visible. The Java multi-file pending list remains unchanged.

The C++ catalog filter fix was deployed in Actions `31017023422`; it does not alter this Java multi-file audit.

## CLI continuation 2026-08-06

- Java IDs `1546,1549,1556,1551,1552,1554,1660,1661,1662,1663,1664,1775,1795,1809` were each attempted in fresh Playwright contexts.
- The formal runner stopped before file-list inspection because the unauthenticated landing page exposed zero programming-navigation buttons. It did not claim file scrolling, independent models, `javac`, Run, Test, Submit, or leakage results.
- Evidence is in `verification-results/programming-workbench-cli-acceptance.json`; screenshots are `verification-screenshots/programming-workbench-random-40/cli-*.png`; trace ZIPs are Git-ignored.
