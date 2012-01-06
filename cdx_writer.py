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

        o = urlparse.urlparse(record.url)
        if 'dns' == o.scheme:
            netloc = o.path
            path   = ''
        else:
            netloc = o.netloc
            path   = o.path.lower()
            if len(path) > 1:
                path = path.rstrip('/')

            if o.query:
                """
                I think the archive's cdx writer is doing the wrong thing here,
                but we will try to maintain compatibility. We really should
                parse the query string BEFORE unquoting. Otherwise, we turn
                encoded arguments into query args when they really are not.
                example url: 'https://twitter.com/intent/session?original_referer=http%3A%2F%2Fplatform.twitter.com%2Fwidgets%2Ftweet_button.html%3Furl%3Dhttp%3A%2F%2Fbit.ly%2FqRht1a%26text%3DAmuse-bouche%3A%2520Bike%2520sharing%2520saves%2520lives%26count%3Dnone&return_to=%2Fintent%2Ftweet'
                "count" shouldn't be a query arg, but since we unquote before
                we parse the string, it becomes one.
                """

                query_list = urlparse.parse_qsl(urlparse.unquote(o.query), keep_blank_values=True)
                joined_tuples = ['='.join(pair) for pair in query_list if pair[1]] + [pair[0] for pair in query_list if not pair[1]]
                joined_tuples.sort()
                path += '?' + '&'.join(joined_tuples).replace(' ', '%20').lower()

        parts = netloc.split('.')

        if 'http' == o.scheme and 'www' == parts[0]:
            parts = parts[1:]

        parts.reverse()
        return ','.join(parts) + ')'+path

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
            if digest.startswith('sha1:'):
                digest = digest[5:]
            return digest
        else:
            h = hashlib.sha1(record.content[1])
            return base64.b32encode(h.digest())

    # get_mime_type() //field "m"
    #___________________________________________________________________________
    def get_mime_type(self, record):
        if 'response' == record.type:
            return record.content_type
        elif 'warcinfo' == record.type:
            return 'warc-info' #why special case this?
        else:
            return 'warc/'+record.type

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

    assert 1 == len(input_files)

    cdx_writer = CDX_Writer(input_files[0], options.format)
    cdx_writer.make_cdx()
