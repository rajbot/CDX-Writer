#!/usr/bin/env python

import os
import commands
from pipes import quote

warc_dir = '/warcs/'

warcs = {'YTV-20120204035110-15431.warc.gz':  '151e5c4b95fde70a9973bd5359b6c6b1',
         'WIDE-20120121174231-03025.warc.gz': '4b4b15279daf06c648563da4d15bf896', #from WIDE-20120121162724-crawl411
        }

for file, hash in warcs.iteritems():
    assert not os.path.exists('tmp.cdx')

    warc_file = quote(warc_dir + file)
    assert os.path.exists(warc_file)

    print "processing", warc_file

    cmd = '../cdx_writer.py %s >tmp.cdx' % warc_file
    print "  running", cmd
    status, output = commands.getstatusoutput(cmd)
    assert 0 == status

    cmd = 'md5sum tmp.cdx'
    print "  running", cmd
    status, output = commands.getstatusoutput(cmd)
    assert 0 == status

    warc_md5 = output.split()[0]

    assert hash == warc_md5

    os.unlink('tmp.cdx')

print "exiting without errors!"
