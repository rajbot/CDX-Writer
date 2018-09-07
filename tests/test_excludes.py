#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest
import py
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

testdir = py.path.local(__file__).dirpath()
datadir = testdir / "small_warcs"
cdx_writer = str(testdir / "../cdx_writer.py")

@pytest.mark.parametrize("test", tests)
def test_exlcudes(test, tmpdir):
    test_file = test['file']
    exclude_list = tmpdir / 'tmp_excludes.txt'
    stats_file   = tmpdir / 'tmp_stats.json'

    assert datadir.join(test_file).exists()

    exclude_list.write(test['exclude'] + '\n')

    cmd = [cdx_writer, '--all-records', '--exclude-list='+str(exclude_list),
           '--stats-file='+str(stats_file), str(test_file)]

    with datadir.as_cwd():
        output = subprocess.check_output(cmd)
    #assert output.strip().endswith(test['result']), """\n  expected: %s\n       got: %s\n""" % (test['result'], '\n'.join(output.split('\n')[1:]))
    assert output == test['result']

    stats = json.loads(stats_file.read_text('utf-8'))

    assert stats['num_records_filtered'] == test['num_filtered']
