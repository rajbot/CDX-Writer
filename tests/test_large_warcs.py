#!/usr/bin/env python

import os
import commands
from pipes import quote

warc_dir = '/warcs/'

warcs = {'YTV-20120204025848-crawl442/YTV-20120204035110-15431.warc.gz':                       'b09c0e4dcd3a9568df30da2aab2f0e06',
         'WIDE-20120121162724-crawl411/WIDE-20120121174231-03025.warc.gz':                     '1bb4004ffc1e9e78b7901ad677b33dae',
         'live-20120312105341306-00165-20120312171822397/live-20120312161414739-00234.arc.gz': '76a2666d5ded179e3534ec85099c268e',
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
