#!/usr/bin/env python3

###############################################################
#
#                       Extract Barcodes
#
###############################################################
# Function:
# To isolate duplex barcodes from paired-end sequence reads and store in FASTQ headers after removal of spacer regions.
#
# Written for Python 3.5.1
#
# USAGE:
# python3 extract_barcodes.py [--read1 READ1] [--read2 READ2] [--outfile OUTFILE] [--blen BARCODELEN] [--slen SPACERLEN]
#                            [--sfilt SPACERFILT]
#
# Arguments:
# --read1 READ1         Input FASTQ file for Read 1 (unzipped)
# --read2 READ2         Input FASTQ file for Read 2 (unzipped)
# --outfile OUTFILE     Output FASTQ files for Read 1 and Read 2 using given filename
# --bpattern BPATTERN   Barcode pattern (N = random barcode bases, A|C|G|T = fixed spacer bases)
# --blist BARCODELIST   List of correct barcodes
#
# Barcode design:
# N = random / barcode bases
# A | C | G | T = Fixed spacer bases
# e.g. ATNNGT means barcode is flanked by two spacers matching 'AT' in front, followed by 'GT'
#
# Inputs:
# 1. A FASTQ file containing first-in-pair (Read 1) reads
# 2. A FASTQ file containing second-in-pair (Read 2) reads
#
# Outputs:
# 1. A Read 1 FASTQ file with barcodes added to the FASTQ header
# 2. A Read 2 FASTQ file with barcodes added to the FASTQ header
# 3. A text file summarizing barcode stats
#
###############################################################

################
#    Modules   #
################
from argparse import ArgumentParser
from itertools import zip_longest
import pandas as pd
import numpy as np
import sys

#######################
#    Helper Function    #
#######################
def find_all(a_str, sub):
    """(str, str) -> int
    Return index of substring in string.
    """
    start = 0
    while True:
        start = a_str.find(sub, start)
        if start == -1: return
        yield start
        start += len(sub)

#######################
#    Main Function    #
#######################
def main():
    # Command-line parameters
    parser = ArgumentParser()
    parser.add_argument("--read1", action="store", dest="read1", type=str,
                        help="Input FASTQ file for Read 1 (unzipped)", required=True)
    parser.add_argument("--read2", action="store", dest="read2", type=str,
                        help="Input FASTQ file for Read 2 (unzipped)", required=True)
    parser.add_argument("--outfile", action="store", dest="outfile", help="Output SSCS BAM file", type=str,
                        required=True)
    parser.add_argument("--bpattern", action="store", dest="bpattern", type=str, required=False,
                        help="Barcode pattern (N = random barcode bases, A|C|G|T = fixed spacer bases) \n"
                             "e.g. ATNNGT means barcode is flanked by two spacers matching 'AT' in front, "
                             "followed by 'GT' \n")
    parser.add_argument("--blist", action="store", dest="blist", type=str, help="List of correct barcodes",
                        required=False)
    args = parser.parse_args()

    ######################
    #       SETUP        #
    ######################
    # === Initialize input and output files ===
    read1 = open(args.read1, "r")
    read2 = open(args.read2, "r")
    r1_output = open('{}_barcode_R1.fastq'.format(args.outfile), "w")
    r2_output = open('{}_barcode_R2.fastq'.format(args.outfile), "w")
    stats = open('{}/barcode_stats.txt'.format(args.outfile.rsplit(sep="/", maxsplit=1)[0]), 'a')

    # === Initialize counters ===
    readpair_count = 0
    bad_spacer = 0
    bad_barcode = 0
    good_barcode = 0

    nuc_lst = ['A', 'C', 'G', 'T', 'N']

    # === Define barcodes ===
    # Check if list of barcodes is provided
    try:
        args.blist
    except NameError:
        args.blist = None

    if args.blist is not None:
        blist = open(args.blist, "r").read().splitlines()
        plen = len(blist[0])

    # Check if barcode pattern is provided
    try:
        args.bpattern
    except NameError:
        args.bpattern = None

    if args.bpattern is not None:
        plen = len(args.bpattern)  # Pattern length
        b_index = list(find_all(args.bpattern, 'N'))  # Index of random barcode bases
        s_index = [x for x in list(range(0, plen)) if x not in b_index]  # Index of constant spacer bases
        spacer = ''.join([args.bpattern[x] for x in s_index])

    # Raise error if neither a barcode list or pattern is provided
    if args.blist is None and args.bpattern is None:
        raise ValueError("No barcode specifications inputted. Please specify barcode list or pattern.")

    # Column in the following corresponds to A, C, G, T, N
    r1_barcode_counter = pd.DataFrame(0, index=np.arange(plen), columns=nuc_lst)
    r2_barcode_counter = pd.DataFrame(0, index=np.arange(plen), columns=nuc_lst)

    ######################
    #  Extract barcodes  #
    ######################
    for r1, r2 in zip(zip_longest(*[read1] * 4), zip_longest(*[read2] * 4)):
        readpair_count += 1

        # Remove new line '\n' from str and separate using variables
        r1_header = r1[0].rstrip()
        r1_seq = r1[1].rstrip()
        r1_qual = r1[3].rstrip()

        r2_header = r2[0].rstrip()
        r2_seq = r2[1].rstrip()
        r2_qual = r2[3].rstrip()

        # Isolate barcode
        r1_barcode = r1_seq[:plen]
        r2_barcode = r2_seq[:plen]

        # Count barcode bases
        for i in range(plen):
            r1_barcode_counter.iloc[i, nuc_lst.index(r1_barcode[i])] += 1
            r2_barcode_counter.iloc[i, nuc_lst.index(r2_barcode[i])] += 1

        # Extract barcode from sequence and quality scores
        r1_seq = r1_seq[plen:]
        r2_seq = r2_seq[plen:]

        r1_qual = r1_qual[plen:]
        r2_qual = r2_qual[plen:]

        # Add barcode and read number to header
        if args.bpattern is not None:
            r1_barcode = ''.join([r1_barcode[x] for x in b_index])
            r2_barcode = ''.join([r2_barcode[x] for x in b_index])

        r1_header = '{}|{}{}/{}'.format(r1_header.split(" ")[0], r1_barcode, r2_barcode, "1")
        r2_header = '{}|{}{}/{}'.format(r2_header.split(" ")[0], r1_barcode, r2_barcode, "2")

        # Isolate barcode
        if args.blist is not None:
            if r1_barcode in blist and r2_barcode in blist:
                good_barcode += 1
                # Write read to output file
                r1_output.write('{}\n{}\n+\n{}\n'.format(r1_header, r1_seq, r1_qual))
                r2_output.write('{}\n{}\n+\n{}\n'.format(r2_header, r2_seq, r2_qual))
            else:
                bad_barcode += 1

        else:
            r1_spacer = ''.join([r1_barcode[x] for x in s_index])
            r2_spacer = ''.join([r2_barcode[x] for x in s_index])

            # Check if spacer is correct
            if r1_spacer == spacer and r2_spacer == spacer:
                # Write read to output file
                r1_output.write('{}\n{}\n+\n{}\n'.format(r1_header, r1_seq, r1_qual))
                r2_output.write('{}\n{}\n+\n{}\n'.format(r2_header, r2_seq, r2_qual))

            else:
                bad_spacer += 1

    r1_output.close()
    r2_output.close()

    # System output
    sys.stderr.write("Total sequences: {}\n".format(readpair_count))
    sys.stderr.write("Missing spacer: {}\n".format(bad_spacer))
    sys.stderr.write("Bad barcodes: {}\n".format(bad_barcode))
    sys.stderr.write("Passing barcodes: {}\n".format(good_barcode))

    # Output stats file
    stats.write("##########\n{}\n##########".format(args.outfile.split(sep="/")[-1]))
    stats.write(
        '\nTotal sequences: {}\nMissing spacer: {}\nBad barcodes: {}\nPassing barcodes: {}\n'.format(readpair_count,
                                                                                                     nospacer,
                                                                                                     bad_barcode,
                                                                                                     good_barcode))
    stats.write('---BARCODE---\n{}\n-----------\n{}\n'.format(r1_barcode_counter.apply(lambda x: x / x.sum(), axis=1),
                                                              r2_barcode_counter.apply(lambda x: x / x.sum(), axis=1)))

    stats.close()


if __name__ == "__main__":
    main()