#!/usr/bin/env python

import pytest
import py
import os
import commands
from pipes import quote

warc_dir = '/warcs/'

if not os.path.isdir(warc_dir):
    pytest.skip(msg="requires large_warcs test dataset")

warcs = {'YTV-20120204025848-crawl442/YTV-20120204035110-15431.warc.gz':                       '8be3352ac814c58e333d1a179e7e7951',
         'WIDE-20120121162724-crawl411/WIDE-20120121174231-03025.warc.gz':                     'c8e315322fa22f84f93f0abd0d414281',
         'live-20120312105341306-00165-20120312171822397/live-20120312161414739-00234.arc.gz': '13dfd294b80d43696e67f60c8f87eb1e',
         'wb_urls.ia11013.20050517055850-c/wb_urls.ia11013.20050805040525.arc.gz':             'f29414651eaced77184a048a2399477c', #missing filedesc:// header
        }

testdir = py.path.local(__file__).dirpath()
cdx_writer = str(testdir / '../cdx_writer.py')

@pytest.mark.parametrize(["file", "hash"], warcs.iteritems())
def test_large_warcs(file, hash, tmpdir):
    warc_file = os.path.join(warc_dir, file)
    assert os.path.exists(warc_file)

    tmpcdx = tmpdir / 'tmp.cdx'

    cmd = '/usr/bin/time --format=%e ' + '%s %s >%s' % (
        cdx_writer, warc_file, tmpcdx)
    print "  running", cmd
    status, output = commands.getstatusoutput(cmd)
    assert 0 == status
    print 'time: ', output
    print 'size: ', os.path.getsize(warc_file)

    cmd = 'md5sum %s' % (tmpcdx,)
    print "  running", cmd
    status, output = commands.getstatusoutput(cmd)
    assert 0 == status

    warc_md5 = output.split()[0]

    assert hash == warc_md5
