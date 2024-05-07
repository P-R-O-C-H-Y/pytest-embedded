# Expecting Functions

While we're doing tests, most of our jobs is to expect a string or a pattern, and do assertions. This is supported by
functions `expect()`, `expect_exact()`, and `expect_unity_test_output()`.

All of these functions share these possible keyword arguments:

-  `timeout`. Set the timeout in seconds for this expect statement. Will throw an `pexpect.TIMEOUT` exception if it exceeded the specified value. (Default: 30 s)
-  `expect_all`. Will match all specified patterns if this is set to True. (Default: False)

## `expect(pattern, **kwargs)`

`pattern` can be `str` or `bytes`, or a compiled regex with `bytes`.

If the pattern is `str` or `bytes`, it will convert to compiled regex with `bytes` and then run the function.

```python
import re

def test_basic_expect(dut):
    dut.write('this would be redirected')

    dut.expect(b'this')
    dut.expect('would')
    dut.expect('[be]{2}')
    dut.expect(re.compile(b'redirected'))
```

If expecting success, the return value would be a `re.Match` object.

```python
def test_expect_return_value(redirect, dut):
    # here we use fixture `redirect` to write the sys.stdout to dut
    with redirect():
        print('this would be redirected')

    res = dut.expect('this (would) be ([cdeirt]+)')
    assert res.group() == b'this would be redirected'
    assert res.group(1) == b'would'
    assert res.group(2).decode('utf-8') == 'redirected'
```

You can get the bytes read before timeout by expecting a `pexpect.TIMEOUT` object

```python
import time
import threading
import pexpect

def test_expect_from_eof(dut):
    def write_bytes():
        for _ in range(5):
            dut.write('1')
            time.sleep(2)

    write_thread = threading.Thread(target=write_bytes, daemon=True)
    write_thread.start()

    res = dut.expect(pexpect.TIMEOUT, timeout=3)
    assert res == b'11'
```

You can also get all bytes in the pexpect process buffer by expecting a `pexpect.EOF` object.

```python
import pexpect

def test_expect_from_eof_current_buffer(dut):
    dut.write('this would be redirected')
    dut.expect('this')

    # close the pexpect process to generate an EOF
    dut.pexpect_proc.terminate()

    res = dut.expect(pexpect.EOF, timeout=None)
    assert res == b' would be redirected'
```

```{eval-rst}

.. note::

    The pexpect process would only read from the process into the buffer when running expecting functions.
    If you're expecting ``pexpect.EOF`` as the first statement, it would return an empty byte string

    .. code-block:: python

        import pexpect

        def test_expect_from_eof_at_first(dut):
            dut.write('this would be redirected')

            # close the pexpect process to generate an EOF
            dut.pexpect_proc.terminate()

            res = dut.expect(pexpect.EOF, timeout=None)
            assert res == b''

```

What's more, argument `pattern` could be a list of all supported types.

```python
import re

def test_expect_from_list(dut):
    dut.write("this would be redirected")

    pattern_list = [
        "this",
        b"would",
        "[be]+",
        re.compile(b"redirected"),
    ]

    for _ in range(4):
        dut.expect(pattern_list)
```

If you set `expect_all` to `True`, the `expect()` function would return with a list of returned values of each item.

## `expect_exact(pattern, **kwargs)`

`pattern` can be `str` or `bytes`.

If the pattern is `str`, would convert to `bytes` and then run the function.

```python
def test_expect_exact(dut):
    dut.write('this would be redirected')

    dut.expect_exact('this would')
    dut.expect_exact(b'be redirected')
```

Same as `expect(pattern, **kwargs)`, argument `pattern` could be a list of all supported types.

```python
def test_expect_exact_from_list(dut):
    dut.write('this would be redirected')

    pattern_list = [
        'this would',
        b'be redirected',
    ]

    for _ in range(2):
        dut.expect_exact(pattern_list)
```

## `expect_unity_test_output(**kwargs)`

[Unity Test](https://github.com/ThrowTheSwitch/Unity) is a c test framework.

This function would parse the output as the unity output. The default value of `timeout` is 60 seconds.

When the test script ends, the DUT object would raise `AssertionError` if any unity test case's result is "FAIL".

What's more, it would dump the junit report under a temp folder and would combine the junit report into the main one if you use `pytest --junitxml` feature.

```python
import inspect
import pytest

def test_expect_unity_test_output_basic(dut):
    dut.write(inspect.cleandoc('''
        foo.c:100:test_case:FAIL:Expected 2 was 1
        foo.c:101:test_case_2:FAIL:Expected 1 was 2
        -------------------
        2 Tests 2 Failures 0 Ignored
        FAIL
    '''))
    with pytest.raises(AssertionError):
        dut.expect_unity_test_output()

    assert len(dut.testsuite.testcases) == 2
    assert dut.testsuite.attrs['failures'] == 2
    assert dut.testsuite.testcases[0].attrs['message'] == 'Expected 2 was 1'
    assert dut.testsuite.testcases[1].attrs['message'] == 'Expected 1 was 2'
```

It also supports [unity fixtures](https://github.com/ThrowTheSwitch/Unity/tree/master/extras/fixture) extra functionality

```python
import inspect
import pytest

def test_expect_unity_test_output_fixture(dut):
    dut.write(inspect.cleandoc('''
        TEST(group, test_case)foo.c:100::FAIL:Expected 2 was 1
        TEST(group, test_case_2)foo.c:101::FAIL:Expected 1 was 2
        -------------------
        2 Tests 2 Failures 0 Ignored
        FAIL
    '''))
    with pytest.raises(AssertionError):
        dut.expect_unity_test_output()

    assert len(dut.testsuite.testcases) == 2
    assert dut.testsuite.attrs['failures'] == 2
    assert dut.testsuite.testcases[0].attrs['message'] == 'Expected 2 was 1'
    assert dut.testsuite.testcases[1].attrs['message'] == 'Expected 1 was 2'
```
