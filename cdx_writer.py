#!/usr/bin/env python

""" This script requires Hanzo Archives' warc-tools:
http://code.hanzoarchives.com/warc-tools/src/tip/hanzo/warctools

This script is loosely based on warcindex.py:
http://code.hanzoarchives.com/warc-tools/src/1897e2bc9d29/warcindex.py
"""
from warctools import ArchiveRecord #from https://bitbucket.org/rajbot/warc-tools
from surt      import surt          #from https://github.com/rajbot/surt

import re
import sys
import base64
import hashlib
import urllib
import urlparse
import lxml.html
from urlparse  import urlsplit
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
        self.crlf_pattern = re.compile('\r?\n\r?\n')

    # parse_robots_meta_tags
    #___________________________________________________________________________
    def parse_robots_meta_tags(self, response_str):
        robot_tags = []
        #print response_str.__repr__()
        ###TODO: this regex seems slow, speed this up.
        headers, html_str = self.crlf_pattern.split(response_str, 1)
        html_str = html_str.strip()


        #print 'headers:'
        #print headers
        #print 'html_str:'
        #print html_str
        #print 'x'

        if '' == html_str:
            return robot_tags

        ###TODO: is there a faster way than actually parsing the html?
        ###maybe use a regex, or maybe just parse the <head.
        html = lxml.html.document_fromstring(html_str)

        try:
            head = html.head
        except IndexError:
            #this might have been an xml response
            return robot_tags

        for meta in head:
            name = meta.get('name')
            if name is not None and 'robots' == name.lower():
                content = meta.get('content')
                if content is not None:
                    tags = content.split(',')
                    tags = [x.strip().lower() for x in tags]
                    robot_tags += tags

        return robot_tags

    # get_AIF_meta_tags() //field "M"
    #___________________________________________________________________________
    def get_AIF_meta_tags(self, record, mime_type):
        """robot metatags, if present, should be in this order: A, F, I
        """
        if 'response' == record.type and 'text/html' == mime_type:
            robot_tags = self.parse_robots_meta_tags(record.content[1])
            if not robot_tags:
                return '-' #common case

            s = ''

            if 'noarchive' in robot_tags:
                s += 'A'
            if 'nofollow' in robot_tags:
                s += 'F'
            if 'noindex' in robot_tags:
                s += 'I'

            if s:
                return ''.join(s)
            else:
                return '-'
        else:
            return '-'


    # get_massaged_url() //field "N"
    #___________________________________________________________________________
    def get_massaged_url(self, record, mime_type):
        if 'warcinfo' == record.type:
            return self.get_original_url(record, mime_type)
        else:
            return surt(record.url)


    # get_compressed_record_size() //field "S"
    #___________________________________________________________________________
    def get_compressed_record_size(self, record, mime_type):
        return str(record.compressed_record_size)

    # get_compressed_arc_file_offset() //field "V"
    #___________________________________________________________________________
    def get_compressed_arc_file_offset(self, record, mime_type):
        return str(self.offset)

    # get_original_url() //field "a"
    #___________________________________________________________________________
    def get_original_url(self, record, mime_type):
        if 'warcinfo' == record.type:
            fake_build_version = "archive-commons.0.0.1-SNAPSHOT-20111218010050"
            url = 'warcinfo:/%s/%s' % (self.file, fake_build_version)
            return url

        return record.url

    # get_date() //field "b"
    #___________________________________________________________________________
    def get_date(self, record, mime_type):
        date = datetime.strptime(record.date, "%Y-%m-%dT%H:%M:%SZ")
        return date.strftime("%Y%m%d%H%M%S")

    # get_file_name() //field "g"
    #___________________________________________________________________________
    def get_file_name(self, record, mime_type):
        return self.file

    # get_new_style_checksum() //field "k"
    #___________________________________________________________________________
    def get_new_style_checksum(self, record, mime_type):
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
    def get_mime_type(self, record, mime_type=None, use_precalulated_mime_type=True):
        """ See the WARC spec for more info on 'application/http; msgtype=response'
        http://archive-access.sourceforge.net/warc/warc_file_format-0.16.html#anchor7
        """

        if use_precalulated_mime_type:
            return mime_type

        if 'response' == record.type and 'application/http; msgtype=response' == record.content_type:
            return self.parse_http_content_type_header(record)
        elif 'response' == record.type:
            return record.content_type
        elif 'warcinfo' == record.type:
            return 'warc-info' #why special case this?
        else:
            return 'warc/'+record.type

    # parse_http_header()
    #___________________________________________________________________________
    def parse_http_header(self, response, header_name):
        pattern = re.compile(header_name+':\s*(.+)', re.I)
        for line in iter(response.splitlines()):
            m = pattern.match(line)
            if m:
                return m.group(1)
        return None

    # parse_http_content_type_header()
    #___________________________________________________________________________
    def parse_http_content_type_header(self, record):
        content_type = self.parse_http_header(record.content[1], 'content-type')
        if content_type is None:
            return 'unk'

        m = re.match('(.+);', content_type)
        if m:
            return m.group(1)
        else:
            return content_type


    # get_redirect() //field "r"
    #___________________________________________________________________________
    def get_redirect(self, record, mime_type):
        response_code = self.get_response_code(record, mime_type)

        if (3 == len(response_code)) and response_code.startswith('3'):
            location = self.parse_http_header(record.content[1], 'location')
            if location:
                # urlparse.urljoin removes blank fragments (trailing #),
                # even if allow_fragments is set to True, so do this manually
                #return urljoin(record.url, location)
                if location.lower().startswith('http'):
                    return location
                else:
                    s = urlsplit(record.url)
                    return s.scheme+'://'+s.netloc+location


        return '-'

    # get_response_code() //field "s"
    #___________________________________________________________________________
    def get_response_code(self, record, mime_type):
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
                #precalculate mime type
                mime_type = self.get_mime_type(record, use_precalulated_mime_type=False)

                s = ''
                for field in self.format.split():
                    if not field in self.field_map:
                        sys.exit('Unknown field: ' + field)

                    endpoint = self.field_map[field].replace(' ', '_')
                    response = getattr(self, 'get_' + endpoint)(record, mime_type)
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
