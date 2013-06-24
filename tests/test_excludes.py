#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import subprocess


tests = [
    {
        'file': 'uncompressed.arc',
        'exclude': 'http://www.sueddeutsche.de',
        'result' : """ CDX N b a m s k r M S V g
filedesc://51_23_20110804181044_crawl101.arc.gz 20110804181044 filedesc://51_23_20110804181044_crawl101.arc.gz warc/filedesc - 3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ - - 161 0 uncompressed.arc
vn,rolo,art)/a/chi-tiet/021826271565622/ngoc-trinh-xinh-tuoi-o-hoi-an 20110804181044 http://art.rolo.vn:80/a/chi-tiet/021826271565622/ngoc-trinh-xinh-tuoi-o-hoi-an unk 404 3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ - - 229 162 uncompressed.arc
com,monsterindia,jobs)/details/9660976.html 20110804181044 http://jobs.monsterindia.com:80/details/9660976.html text/html 200 BQJDX42R5GFX4OIXPGNHZG3QFM5X3KQR - - 51406 79332 uncompressed.arc
""",
        'num_filtered': 1,
    },
    {
        'file': 'uncompressed.arc',
        'exclude': 'http://art.rolo.vn/a/',
        'result' : """ CDX N b a m s k r M S V g
filedesc://51_23_20110804181044_crawl101.arc.gz 20110804181044 filedesc://51_23_20110804181044_crawl101.arc.gz warc/filedesc - 3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ - - 161 0 uncompressed.arc
de,sueddeutsche)/muenchen/manu-chao-in-muenchen-che-guitarra-1.1114509-2 20110804181044 http://www.sueddeutsche.de:80/muenchen/manu-chao-in-muenchen-che-guitarra-1.1114509-2 text/html 200 ZMBIXCVTXG2CNEFAZI753FJUXJUQSI2M - A 78939 392 uncompressed.arc
com,monsterindia,jobs)/details/9660976.html 20110804181044 http://jobs.monsterindia.com:80/details/9660976.html text/html 200 BQJDX42R5GFX4OIXPGNHZG3QFM5X3KQR - - 51406 79332 uncompressed.arc
""",
        'num_filtered': 1,
    },
    {
        'file': 'uncompressed.arc',
        'exclude': 'http://www.sueddeutsche.de\n\nhttp://art.rolo.vn/a/', #contains repeated newline
        'result' : """ CDX N b a m s k r M S V g
filedesc://51_23_20110804181044_crawl101.arc.gz 20110804181044 filedesc://51_23_20110804181044_crawl101.arc.gz warc/filedesc - 3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ - - 161 0 uncompressed.arc
com,monsterindia,jobs)/details/9660976.html 20110804181044 http://jobs.monsterindia.com:80/details/9660976.html text/html 200 BQJDX42R5GFX4OIXPGNHZG3QFM5X3KQR - - 51406 79332 uncompressed.arc
""",
        'num_filtered': 2,
    }
]

test_num = 0
for test in tests:
    test_file = test['file']
    exclude_list = 'tmp_excludes.txt'
    stats_file   = 'tmp_stats.json'

    assert os.path.exists(test_file)
    assert not os.path.exists(exclude_list)
    assert not os.path.exists(stats_file)

    print "processing #", test_num, test_file

    f = open(exclude_list, 'w')
    f.write(test['exclude'] + '\n')
    f.close()

    cmd = ['../cdx_writer.py', '--all-records', '--exclude-list='+exclude_list, '--stats-file='+stats_file, test_file]

    output = subprocess.check_output(cmd)
    #assert output.strip().endswith(test['result']), """\n  expected: %s\n       got: %s\n""" % (test['result'], '\n'.join(output.split('\n')[1:]))
    assert output == test['result'], """\n  expected: %s\n       got: %s\n""" % (test['result'], output)

    stats_fh = open(stats_file)
    stats = json.load(stats_fh)
    stats_fh.close()
    assert stats['num_records_filtered'] == test['num_filtered'], "Wrong number of records were filtered! expected %d got %d" % (test['num_filtered'], stats['num_records_filtered'])

    os.unlink(exclude_list)
    os.unlink(stats_file)
    test_num += 1
print "exiting without errors!"
