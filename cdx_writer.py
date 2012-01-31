#!/usr/bin/env python

""" This script requires a modified version of Hanzo Archives' warc-tools:
http://code.hanzoarchives.com/warc-tools/src/tip/hanzo/warctools

This script is loosely based on warcindex.py:
http://code.hanzoarchives.com/warc-tools/src/1897e2bc9d29/warcindex.py

The functions that start with "get_" (as opposed to "parse_") are called be the
dispatch loop in make_cdx using getattr().
"""
from warctools import ArchiveRecord #from https://bitbucket.org/rajbot/warc-tools
from surt      import surt          #from https://github.com/rajbot/surt

import os
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
    def __init__(self, file, format, use_full_path=False, file_prefix=None):

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
        self.crlf_pattern = re.compile('\r?\n\r?\n')

        #this is what wayback uses:
        self.fake_build_version = "archive-commons.0.0.1-SNAPSHOT-20120112102659"

        #these fields are set for each record in the warc
        self.offset        = 0
        self.mime_type     = None
        self.headers       = None
        self.content       = None
        self.meta_tags     = None
        self.response_code = None

        #Large html files cause lxml to segfault
        #problematic file was 154MB, we'll stop at 5MB
        self.lxml_parse_limit = 5 * 1024 * 1024

        if use_full_path:
            self.warc_path = os.path.abspath(file)
        elif file_prefix:
            self.warc_path = os.path.join(file_prefix, file)
        else:
            self.warc_path = file

    # parse_http_header()
    #___________________________________________________________________________
    def parse_http_header(self, header_name):
        if self.headers is None:
            return None

        pattern = re.compile(header_name+':\s*(.+)', re.I)
        for line in iter(self.headers):
            m = pattern.match(line)
            if m:
                return m.group(1)
        return None

    # parse_http_content_type_header()
    #___________________________________________________________________________
    def parse_http_content_type_header(self, record):
        content_type = self.parse_http_header('content-type')
        if content_type is None:
            return 'unk'

        # some http responses end abruptly: ...Content-Length: 0\r\nConnection: close\r\nContent-Type: \r\n\r\n\r\n\r\n'
        content_type = content_type.strip()
        if '' == content_type:
            return 'unk'

        m = re.match('(.+?);', content_type)
        if m:
            return m.group(1)
        else:
            return content_type

    # parse_meta_tags
    #___________________________________________________________________________
    def parse_meta_tags(self, record):
        """We want to parse meta tags in <head>, even if not direct children.
        e.g. <head><noscript><meta .../></noscript></head>

        What should we do about multiple meta tags with the same name?
        currently, we append the content attribs together with a comma seperator.

        We use either the 'name' or 'http-equiv' attrib as the meta_tag dict key.
        """

        if not ('response' == record.type and 'text/html' == self.mime_type):
            return None

        meta_tags = {}

        #lxml.html can't parse blank documents
        html_str = self.content.strip()
        if '' == html_str:
            return meta_tags

        #lxml can't handle large documents
        if record.content_length > self.lxml_parse_limit:
            return meta_tags

        ###TODO: is there a faster way than actually parsing the html?
        ###maybe use a regex, or maybe just parse the <head>.
        try:
            html = lxml.html.document_fromstring(html_str)
        except lxml.etree.ParserError:
            return meta_tags

        try:
            head = html.head
        except IndexError:
            #this might have been an xml response
            return meta_tags

        metas = head.xpath("//meta")
        for meta in metas:
            name = meta.get('name')
            if name is None:
                name = meta.get('http-equiv')

            if name is not None:
                name = name.lower()
                try:
                    content = meta.get('content')
                except UnicodeDecodeError:
                    continue
                if content is not None:
                    if name not in meta_tags:
                        meta_tags[name] = content
                    else:
                        meta_tags[name] += ',' + content

        return meta_tags


    # get_AIF_meta_tags() //field "M"
    #___________________________________________________________________________
    def get_AIF_meta_tags(self, record):
        """robot metatags, if present, should be in this order: A, F, I
        """
        x_robots_tag = self.parse_http_header('x-robots-tag')

        if x_robots_tag is None:
            if not self.meta_tags:
                return '-'
            if 'robots' not in self.meta_tags:
                return '-'

        robot_tags = []
        if self.meta_tags and 'robots' in self.meta_tags:
            robot_tags += self.meta_tags['robots'].split(',')
        if x_robots_tag:
            robot_tags += x_robots_tag.split(',')
        robot_tags = [x.strip().lower() for x in robot_tags]

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
            url = 'warcinfo:/%s/%s' % (self.file, self.fake_build_version)
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
        return self.warc_path

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
    def get_mime_type(self, record, use_precalculated_value=True):
        """ See the WARC spec for more info on 'application/http; msgtype=response'
        http://archive-access.sourceforge.net/warc/warc_file_format-0.16.html#anchor7
        """

        if use_precalculated_value:
            return self.mime_type

        if 'response' == record.type and 'application/http; msgtype=response' == record.content_type:
            return self.parse_http_content_type_header(record)
        elif 'response' == record.type:
            return record.content_type
        elif 'warcinfo' == record.type:
            return 'warc-info' #why special case this?
        else:
            return 'warc/'+record.type

    # urljoin_with_fragments()
    #___________________________________________________________________________
    def urljoin_with_fragments(self, base, url):
        """urlparse.urljoin removes blank fragments (trailing #),
        even if allow_fragments is set to True, so do this manually
        """
        if url.lower().startswith('http'):
            return url.replace(' ', '%20')
        else:
            if not url.startswith('/'):
                url = '/'+url
            s = urlsplit(base)
            abs_url = s.scheme+'://'+s.netloc+url
            return abs_url.replace(' ', '%20')


    # get_redirect() //field "r"
    #___________________________________________________________________________
    def get_redirect(self, record):
        response_code = self.response_code

        ## It turns out that the refresh tag is being used in both 2xx and 3xx
        ## responses, so always check both the http location header and the meta
        ## tags. Also, the java version passes spaces through to the cdx file,
        ## which might break tools that split cdx lines on whitespace.

        #only deal with 2xx and 3xx responses:
        #if 3 != len(response_code):
        #    return '-'

        #if response_code.startswith('3'):
        location = self.parse_http_header('location')
        if location:
            return self.urljoin_with_fragments(record.url, location)
        #elif response_code.startswith('2'):
        if self.meta_tags and 'refresh' in self.meta_tags:
            redir_loc = self.meta_tags['refresh']
            m = re.search('\d+;\s*url=(.+)', redir_loc, re.I) #url might be capitalized
            if m:
                return self.urljoin_with_fragments(record.url, m.group(1))

        return '-'

    # get_response_code() //field "s"
    #___________________________________________________________________________
    def get_response_code(self, record, use_precalculated_value=True):
        if use_precalculated_value:
            return self.response_code

        if 'response' != record.type:
            return '-'

        m = re.match("HTTP/\d\.\d (\d+)", record.content[1])
        if m:
            return m.group(1)
        else:
            return '-'

    # split_headers_and_content()
    #___________________________________________________________________________
    def parse_headers_and_content(self, record):
        """Returns a list of header lines, split with splitlines(), and the content.
        We call splitlines() here so we only split once, and so \r\n and \n are
        split in the same way.
        """

        if 'response' == record.type and record.content[1].startswith('HTTP'):
            headers, content = self.crlf_pattern.split(record.content[1], 1)
            headers = headers.splitlines()
        else:
            headers = None
            content = None

        return headers, content

    # make_cdx()
    #___________________________________________________________________________
    def make_cdx(self):
        print ' CDX ' + self.format #print header

        fh = ArchiveRecord.open_archive(self.file, gzip="auto", mode="r")
        for (offset, record, errors) in fh.read_records(limit=None, offsets=True):
            self.offset = offset

            if record:
                ### precalculated data that is used multiple times
                self.headers, self.content = self.parse_headers_and_content(record)
                self.mime_type             = self.get_mime_type(record, use_precalculated_value=False)
                self.response_code         = self.get_response_code(record, use_precalculated_value=False)
                self.meta_tags             = self.parse_meta_tags(record)

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
                pass # tail

        fh.close()

# main()
#_______________________________________________________________________________
if __name__ == '__main__':

    parser = OptionParser(usage="%prog [options] warc.gz")
    parser.set_defaults(format        = "N b a m s k r M S V g",
                        use_full_path = False,
                        file_prefix   = None,
                       )

    parser.add_option("--format",  dest="format", help="A space-separated list of fields [default: '%default']")
    parser.add_option("--use-full-path", dest="use_full_path", action="store_true", help="Use the full path of the warc file in the 'g' field")
    parser.add_option("--file-prefix",   dest="file_prefix", help="Path prefix for warc file name in the 'g' field."
                      " Useful if you are going to relocate the warc.gz file after processing it."
                     )

    (options, input_files) = parser.parse_args(args=sys.argv[1:])

    if not 1 == len(input_files):
        parser.print_help()
        exit(-1)

    cdx_writer = CDX_Writer(input_files[0], options.format,
                            use_full_path = options.use_full_path,
                            file_prefix   = options.file_prefix,
                           )
    cdx_writer.make_cdx()
