# Workbench online acceptance follow-up (3)

- Auth probe: passed; existing storageState reused; no re-login.

| Language | Exercise | Status | Run | Public | Submit | Hidden leakage |
|---|---:|---|---|---|---|---|
| Java | 1546 | failed | exit event missing | 3/3 | 8/8 | 0 |
| C++ | 1734 | passed | exit_code=0 | 3/3 | 8/8 | 0 |
| Python | 1629 | passed | exit_code=0 | 3/3 | 8/8 | 0 |

- Java 1546: five files, file-list scroll, save, public 3/3, submit 8/8 passed; interactive exit event remains missing.
- C++ 1734: stdout and exit_code 0, public 3/3, submit 8/8 passed.
- Python 1629: stdout w and exit_code 0, public 3/3, submit 8/8 passed.
