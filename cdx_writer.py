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
import urllib
import urlparse
from datetime  import datetime
from optparse  import OptionParser
from surt      import surt

class CDX_Writer(object):

    #___________________________________________________________________________
    def __init__(self, file, format):

        self.field_map = {'M': 'AIF meta tags',
                          'N': 'massaged url',
                          'S': 'compressed record size',
                          'V': 'compressed arc file offset',
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
        self.offset = 0


    # get_AIF_meta_tags() //field "M"
    #___________________________________________________________________________
    def get_AIF_meta_tags(self, record):
        return '-'


    # get_massaged_url() //field "N"
    #___________________________________________________________________________
    def get_massaged_url(self, record):
        if 'warcinfo' == record.type:
            return self.get_original_url(record)
        else:
            return surt(record.url)


    # get_compressed_record_size() //field "S"
    #___________________________________________________________________________
    def get_compressed_record_size(self, record):
        return str(record.compressed_record_size)

    # get_compressed_arc_file_offset() //field "V"
    #___________________________________________________________________________
    def get_compressed_arc_file_offset(self, record):
        return str(self.offset)

    # get_original_url() //field "a"
    #___________________________________________________________________________
    def get_original_url(self, record):
        if 'warcinfo' == record.type:
            fake_build_version = "archive-commons.0.0.1-SNAPSHOT-20111218010050"
            url = 'warcinfo:/%s/%s' % (self.file, fake_build_version)
            return url

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
        """Return a base32-encoded sha1
        For revisit records, return the original sha1
        """

        if 'revisit' == record.type:
            digest = record.get_header('WARC-Payload-Digest')
            return digest.replace('sha1:', '')
        elif 'response' == record.type and 'application/http; msgtype=response' == record.content_type:
            # Where does this WARC-Payload-Digest header come from?
            # It does not match the sha1(record.content[1]), which might
            # have something to do with the different content-type headers
            # in the warc header and the actual http response
            digest = record.get_header('WARC-Payload-Digest')
            return digest.replace('sha1:', '')
        else:
            h = hashlib.sha1(record.content[1])
            return base64.b32encode(h.digest())

    # get_mime_type() //field "m"
    #___________________________________________________________________________
    def get_mime_type(self, record):
        # 'application/http; msgtype=response' is a strange special-case...
        if 'response' == record.type and 'application/http; msgtype=response' == record.content_type:
            return self.get_parsed_content_type(record)
        elif 'response' == record.type:
            return record.content_type
        elif 'warcinfo' == record.type:
            return 'warc-info' #why special case this?
        else:
            return 'warc/'+record.type

    # get_parsed_content_type()
    #___________________________________________________________________________
    def get_parsed_content_type(self, record):
        """Sometimes the WARC 'Content-Type' header contains
        'application/http; msgtype=response', which does not match the
        Content-Type header of the http response. We want to write the header
        contained in the actual response into the CDX.
        """

        content_type = record.type
        for line in record.content[1].splitlines():
            if line.startswith('Content-Type: '):
                content_type = line.replace('Content-Type: ', '')
                break

        m = re.match('(.+);', content_type)
        if m:
            return m.group(1)
        else:
            return content_type



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
        if 'response' != record.type:
            return '-'

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
            self.offset = offset

            if record:
                s = ''
                for field in self.format.split():
                    if not field in self.field_map:
                        sys.exit('Unknown field: ' + field)

                    endpoint = self.field_map[field].replace(' ', '_')
                    response = getattr(self, 'get_' + endpoint)(record)
                    s += response + ' '

                print s.rstrip()
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

    (options, input_files) = parser.parse_args(args=sys.argv[1:])

    if not 1 == len(input_files):
        parser.print_help()
        exit(-1)

    cdx_writer = CDX_Writer(input_files[0], options.format)
    cdx_writer.make_cdx()
