#!/usr/bin/env python

""" This script requires Hanzo Archives' warc-tools:
http://code.hanzoarchives.com/warc-tools/src/tip/hanzo/warctools

This script is loosely based on warcindex.py:
http://code.hanzoarchives.com/warc-tools/src/1897e2bc9d29/warcindex.py
"""
import sys
from urlparse  import urlparse
from datetime  import datetime
from warctools import ArchiveRecord
from optparse  import OptionParser

class CDX_Writer(object):

    #___________________________________________________________________________
    def __init__(self, file, format):

        self.field_map = {'N': 'massaged url',
                          'a': 'original url',
                          'b': 'date',
                          'g': 'file name',
                          'm': 'mime type',
                         }

        self.file   = file
        self.format = format

    # get_massaged_url() //field "N"
    #___________________________________________________________________________
    def get_massaged_url(self, record):
        o = urlparse(record.url)
        if 'dns' == o.scheme:
            netloc = o.path
            path   = ''
        else:
            netloc = o.netloc
            path   = o.path

        parts = netloc.split('.')
        parts.reverse()
        return ','.join(parts) + ')'+path


    # get_original_url() //field "a"
    #___________________________________________________________________________
    def get_original_url(self, record):
        return record.url

    # get_date() //field "b"
    #___________________________________________________________________________
    def get_date(self, record):
        date = datetime.strptime(record.date, "%Y-%m-%dT%H:%M:%SZ")
        return date.strftime("%Y%m%d%H%M%S")

    # get_file_name() //field "g"
    #___________________________________________________________________________
    def get_file_name(self, record):
        return self.file

    # get_mime_type() //field "m"
    #___________________________________________________________________________
    def get_mime_type(self, record):
        return record.content_type

    # make_cdx()
    #___________________________________________________________________________
    def make_cdx(self):
        print ' CDX ' + self.format #print header

        fh = ArchiveRecord.open_archive(self.file, gzip="auto")
        for (offset, record, errors) in fh.read_records(limit=None, offsets=True):
            if record:
                if 'warcinfo' == record.type:
                    continue

                str = ''
                for field in self.format.split():

                    if not field in self.field_map:
                        sys.exit('Unknown field: ' + field)

                    endpoint = self.field_map[field].replace(' ', '_')
                    response = getattr(self, 'get_' + endpoint)(record)
                    str += response + ' '

                print str.rstrip()
                #record.dump()
            elif errors:
                pass # ignore
            else:
                pass            # no errors at tail

        fh.close()

# main()
#_______________________________________________________________________________
if __name__ == '__main__':

    parser = OptionParser(usage="%prog [options] warc")

    parser.add_option("-f", "--format", dest="format")

    parser.set_defaults(format="N b a m s k r M S V g")
    parser.set_defaults(format="N b a m g")

    (options, input_files) = parser.parse_args(args=sys.argv[1:])

    assert 1 == len(input_files)

    cdx_writer = CDX_Writer(input_files[0], options.format)
    cdx_writer.make_cdx()
