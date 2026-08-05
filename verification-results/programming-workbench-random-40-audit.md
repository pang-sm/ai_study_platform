# programming-workbench-random-40 audit

Status: incomplete_browser_tool_timeout
Base URL: http://101.32.190.42/
Browser: Codex In-app Browser

Existing confirmed records remain unchanged: 13 prior records, including the previously recorded C/C++/Python results. Statsig and ab.chatgpt.com telemetry repeatedly timed out and are not treated as site responses.

## New record

| language | exercise_id | title | run | public | submit | status |
|---|---:|---|---|---|---|---|
|Java|1660|Cinema seat booking|exit -9|1/3|4/8|failed|
|Java|1661|Library lending registration|unstable|0/3|2/8|failed|
|Java|1662|Parking fee policy|unstable|0/3|0/8|failed|
|Java|1663|Restaurant reservation queue|exit -9|0/3|0/8|failed|
|Java|1664|Student course registration|not verified|n/a|n/a|failed: Test/Submit controls missing|
|Java|1546|Library lending registration|not captured|not executed|not executed|failed: Test timed out twice; controls disappeared from DOM|
|Java|1549|Student course registration|not captured|not executed|not executed|failed: Test timed out twice; browser kernel reset|
|Java|1551|E-commerce order and coupon|not verified|n/a|n/a|failed: Test/Submit controls missing|
|Java|1552|Hotel room booking|not verified|n/a|n/a|failed: Test/Submit controls missing|
|Java|1554|Board game ranking|not verified|n/a|n/a|failed: Test/Submit controls missing|
|Java|1556|Parcel sorting and delivery|exit -9|not verified|not verified|failed: Test action timeout|

The six-file Java menu was visible and Main.java was marked as the entry file. Movie.java starter contained a complete implementation and no TODO. Valid booking cases returned REJECTED. The terminal disconnected after sample input. No reference or hidden test content was visible.

1661 showed five editable files and TODOs in Book.java. All three public cases returned REJECTED; the terminal showed running and failed without reliable stdout. No reference or hidden test content was visible.

1662 showed seven editable files. BaseFeePolicy.java had a TODO framework. All public and full tests returned PARKED null 0; the terminal disconnected/failed. No reference or hidden test content was visible.

1663 showed six editable files including an enum. The terminal reported exit_code -9 after sample input; public and full tests returned empty actual output. No reference or hidden test content was visible.

1664 showed five editable files and TODOs, but no statement, samples, Test button, or Submit button. Only Run was visible. Current URL: http://101.32.190.42/.

1546 showed five editable files, Book.java TODOs, three public samples with explanations, and no hidden/reference content. The top Test action timed out twice; after retries Test and Submit disappeared from the DOM. Run, public tests and submit remain unverified. Current URL: http://101.32.190.42/. Console/Network showed only Statsig telemetry timeouts.

1549 showed five editable files, Course.java TODOs, three public samples with explanations, and no hidden/reference content. Test was attempted twice but timed out and reset the browser kernel before a result could be read. Run, public tests and submit remain unverified. Current URL: http://101.32.190.42/. Console/Network showed only Statsig telemetry timeouts.

1551 showed six editable files and TODOs, but no statement, samples, Test button, or Submit button. Only Run was visible. Current URL: http://101.32.190.42/.

1552 showed five editable files and TODOs, but no statement, samples, Test button, or Submit button. Only Run was visible. Current URL: http://101.32.190.42/.

1554 showed four editable files and TODOs, but no statement, samples, Test button, or Submit button. Only Run was visible. Current URL: http://101.32.190.42/.

1556 showed five editable Java files (DeliveryStatus.java, DispatchCenter.java, Main.java, Parcel.java, Route.java), three public samples, and sample explanations. The starter contained TODOs. Run executed but the terminal disconnected with exit_code -9. The correct top Test action timed out on two attempts while the result panel/page state was active; Submit and public-test results were not verified. Console showed only Statsig telemetry timeouts. Screenshot: `verification-screenshots/programming-workbench-random-40/java-1556-run-test-timeout.png`. URL: http://101.32.190.42/.

Remaining current sample work: Java 1549, 1551, 1552, 1554, 1556 and the remaining Java/C++/Python items from the prior manifest. 1546 and 1549 UI content was rechecked, but execution/test/submit remains incomplete. C is not rerun.

## Continuation 2026-08-05

- Java 1809: after correcting the required trailing space, the official submission modal showed 8/8; all three public cases showed real input, expected output, actual output, exit code 0, and duration. Interactive Run was not captured. Hidden details were not visible.
- C++ filter regression: switching from the stale Python list to C++ and paginating could briefly show the prior language's cards. This was reproduced as a stale list-response race and fixed in `frontend/src/components/ProgrammingHome.jsx` by invalidating pending requests and resetting to page 1 on language change. `npm run build` passed locally.
- The remaining C++ IDs 1734, 1756, 1758, 1762, and 1767 were not counted as verified because the browser context was consumed by the reproduced filter race before their individual Workbench runs could be completed.
- Deployment follow-up: Actions run `31017023422` completed successfully for commit `7cda62c`. After a fresh page load, C++ selection showed C++ cards and no Python cards; moving to page 2 continued to show C++ cards. This validates the filter/pagination fix only, not the five remaining exercise workflows.
