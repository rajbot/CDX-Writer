#!/usr/bin/env python

""" This script requires Hanzo Archives' warc-tools:
http://code.hanzoarchives.com/warc-tools/src/tip/hanzo/warctools

This script is loosely based on warcindex.py:
http://code.hanzoarchives.com/warc-tools/src/1897e2bc9d29/warcindex.py
"""
from warctools import ArchiveRecord

import re
import sys
import base64
import hashlib
from urlparse  import urlparse
from datetime  import datetime
from optparse  import OptionParser

class CDX_Writer(object):

    #___________________________________________________________________________
    def __init__(self, file, format):

        self.field_map = {'N': 'massaged url',
                          'a': 'original url',
                          'b': 'date',
                          'g': 'file name',
                          'k': 'new style checksum',
                          'm': 'mime type',
                          'r': 'redirect',
                          's': 'response code',
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

    # get_new_style_checksum() //field "k"
    #___________________________________________________________________________
    def get_new_style_checksum(self, record):
        """Return a base32-encoded sha1"""
        h = hashlib.sha1(record.content[1])
        return base64.b32encode(h.digest())

    # get_mime_type() //field "m"
    #___________________________________________________________________________
    def get_mime_type(self, record):
        return record.content_type

    # get_redirect() //field "r"
    #___________________________________________________________________________
    def get_redirect(self, record):
        response_code = self.get_response_code(record)

        if (3 == len(response_code)) and response_code.startswith('3'):
            m = re.search("Location: (\S+)", record.content[1])
            if m:
                return m.group(1)

        return '-'

    # get_response_code() //field "s"
    #___________________________________________________________________________
    def get_response_code(self, record):
        m = re.match("HTTP/\d\.\d (\d+)", record.content[1])
        if m:
            return m.group(1)
        else:
            return '-'

    # make_cdx()
    #___________________________________________________________________________
    def make_cdx(self):
        print ' CDX ' + self.format #print header

        fh = ArchiveRecord.open_archive(self.file, gzip="auto")
        for (offset, record, errors) in fh.read_records(limit=None, offsets=True):
            if record:
                if 'response' != record.type:
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
    parser.set_defaults(format="N b a m s k r g")

    (options, input_files) = parser.parse_args(args=sys.argv[1:])

    assert 1 == len(input_files)

    cdx_writer = CDX_Writer(input_files[0], options.format)
    cdx_writer.make_cdx()
