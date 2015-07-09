# Testing cdx_writer

Use ``py.test`` to run automated tests.

``test_small_warcs.py`` and ``test_excludes.py`` uses test data in
``small_warcs`` directory. py.test will always run these tests.

``test_large_warcs.py`` will run only when test web archive data
is setup in ``/warcs`` (currently hard-coded and test will fail if
you change it, because path is included in the expected output).

## Downloadin Test W/ARCs

To download test web archive for ``test_large_warcs.py``, follow these steps:

    sudo mkdir /warcs
	sudo chown <your uid> /warcs

Save your IA auth cookies in Mozilla-style cookiejar file ``~/.iaauth``
(You can do this with ``curl``). Then:

	python tests/test_large_warcs.py download

``test_large_warcs.py`` has two additional sub-commands ``cdx`` and ``exp``.
They are meant for helping update test output expectation files (``*.exp``).

## Updating Expected Output

Currently, output of ``test_large_warcs.py`` is checked with two methods:

- Comparing MD5 hash of whole CDX with expected value specified in ``warcs``
  variable.
- Comparing output CDX with ``large_warcs/*/*.exp``, line by line.

Each ``.exp`` file has the expected CDX lines, in which ``urlkey`` and
``original`` fields (1st and 3rd column) are replaced by MD5 hash of the
original value. So, ``test_arge_warcs.py`` runs the same transformation
on the ``cdx_writer`` output, then runs ``diff -u`` command on them.

When expected output changes because of bug fix etc., update the whole-file
MD5 hash and corresponding ``.exp`` files. If either ``urlkey`` or
``original`` field changes, you'd need to update their MD5 hashes in ``.exp``
files. In such a situation, it is easier to generate ``.exp`` file from
expected CDX:

    python tests/test_large_warcs.py cdx
	... edit generated .cdx ....
	python tests/test_large_warcs.py exp
