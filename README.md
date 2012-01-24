Python script to create CDX index files of WARC data.

Usage: `cdx_writer.py [options] warc.gz`

Options:
    -h, --help            show this help message and exit
    -f FORMAT, --format=FORMAT
                          A space-separated list of fields [default: 'N b a m s k r M S V g']
    --use-full-path       Use the full path of the warc file in the 'g' field
    --use-item-path       Use IA item path of the warc file in the 'g' field.
                          Similar to --use-full-path, but removes /n/items/ prefix from file path.

Output is written to stdout. The first line of output is the CDX header.
This header line begins with a space so that the cdx file can be passed
through `sort` while keeping the header at the top.

The supported format options are:

    M meta tags (AIF) *
    N massaged url
    S compressed record size
    V compressed arc file offset *
    a original url **
    b date **
    g file name
    k new style checksum *
    m mime type of original document *
    r redirect *
    s response code *

    * in alexa-made dat file
    ** in alexa-made dat file meta-data line

More information about the CDX format syntax can be found here:
http://www.archive.org/web/researcher/cdx_legend.php
