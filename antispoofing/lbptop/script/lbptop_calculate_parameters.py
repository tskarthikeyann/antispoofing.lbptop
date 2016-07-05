#!/usr/bin/env python
# Tiago de Freitas Pereira <tiagofrepereira@gmail.com>
# Fri Jul 13 14:30:00 CEST 2012

"""Calculates the LBPTop planes (XY,XT,YT) of the normalized faces in the videos in the REPLAY-ATTACK and CASIA-FASD and MSU-MFSD database. This code extract the LBP-TOP features using the MULTIRESOLUTION approach, setting more than one value for Rt. The result is the LBP histogram over all orthogonal frames of the video (XY,XT,YT). Different types of LBP operators are supported. The histograms can be computed for a subset of the videos in the database (using the protocols in REPLAY-ATTACK). The output is a single .hdf5 file for each video. The procedure is described in the paper: "LBP-TOP based countermeasure against facial spoofing attacks" - de Freitas Pereira, Tiago and Anjos, Andre and De Martino, Jose Mario and Marcel, Sebastien; ACCV - LBP 2012

"""

import os, sys
import argparse
import bob.ip.base
import bob.io.video
import bob.ip.color
import numpy

from .. import spoof
import antispoofing.utils
import string

import antispoofing.utils.faceloc as faceloc
from antispoofing.utils.faceloc import *
from antispoofing.lbptop.helpers import *
from antispoofing.utils.db import *


def main():
    basedir = os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0])))

    INPUT_DIR = os.path.join(basedir, 'database')
    OUTPUT_DIR = os.path.join(basedir, 'lbptop_features')

    ##########
    # General configuration
    ##########

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('input_dir', metavar='DIR', type=str, default=INPUT_DIR,
                        help='Base directory containing the videos to be treated by this procedure (defaults to "%(default)s")')

    parser.add_argument('output_dir', metavar='DIR', default=OUTPUT_DIR,
                        help="This path will be prepended to every file output by this procedure (defaults to '%(default)s')")

    parser.add_argument('-n', '--normface-size', dest="normfacesize", default=[64, ], type=int,
                        help="this is the size of the normalized face box if face normalization is used. If more values are given, then the first one corresponds to height, and the second to the width (defaults to '%(default)s')",
                        nargs='+')

    parser.add_argument('--ff', '--facesize_filter', dest="facesize_filter", default=50, type=int,
                        help="all the frames with faces smaller then this number, will be discarded (defaults to '%(default)s')")

    parser.add_argument('-t', '--tan-triggs', dest='tan_triggs', action='store_true', default=False,
                        help="Apply the Tan & Triggs algorithm before LBP-TOP")

    lbptype = ['regular', 'riu2', 'uniform']
    parser.add_argument('-lXY', '--lbptypeXY', metavar='LBPTYPE', type=str, choices=lbptype, default='uniform',
                        dest='lbptypeXY',
                        help='Choose the type of LBP to use in the XY plane (defaults to "%(default)s"). Allowed values are: ' + str(
                            lbptype))
    parser.add_argument('-lXT', '--lbptypeXT', metavar='LBPTYPE', type=str, choices=lbptype, default='uniform',
                        dest='lbptypeXT',
                        help='Choose the type of LBP to use in the XT plane (defaults to "%(default)s"). Allowed values are: ' + str(
                            lbptype))
    parser.add_argument('-lYT', '--lbptypeYT', metavar='LBPTYPE', type=str, choices=lbptype, default='uniform',
                        dest='lbptypeYT',
                        help='Choose the type of LBP to use in the YT plane (defaults to "%(default)s"). Allowed values are: ' + str(
                            lbptype))

    parser.add_argument('-nXY', '--neighborsXY', type=int, default=8, dest='nXY',
                        help='Number of Neighbors in the XY plane (defaults to "%(default)s")')
    parser.add_argument('-nXT', '--neighborsXT', type=int, default=8, dest='nXT',
                        help='Number of Neighbors in the XT plane (defaults to "%(default)s")')
    parser.add_argument('-nYT', '--neighborsYT', type=int, default=8, dest='nYT',
                        help='Number of Neighbors in the YT plane (defaults to "%(default)s")')

    parser.add_argument('-rX', '--radiusX', type=int, default=1, dest='rX',
                        help='Radius of the X axis (defaults to "%(default)s")')
    parser.add_argument('-rY', '--radiusY', type=int, default=1, dest='rY',
                        help='Radius of the Y axis (defaults to "%(default)s")')
    parser.add_argument('-rT', '--radiusT', type=int, default=(1,), dest='rT',
                        help='Set of radius of the T axis (defaults to "%(default)s")', choices=xrange(10), nargs='+')

    elbptype = ['regular', 'transitional', 'direction_coded', 'modified']
    parser.add_argument('-eXY', '--elbptypeXY', metavar='ELBPTYPE', type=str, choices=elbptype, default='regular',
                        dest='elbptypeXY',
                        help='Choose the type of extended LBP features to compute in the XY plane (defaults to "%(default)s"). Allowed values are: ' + str(
                            elbptype))

    parser.add_argument('-eXT', '--elbptypeXT', metavar='ELBPTYPE', type=str, choices=elbptype, default='regular',
                        dest='elbptypeXT',
                        help='Choose the type of extended LBP features to compute in the XT plane (defaults to "%(default)s"). Allowed values are: ' + str(
                            elbptype))

    parser.add_argument('-eYT', '--elbptypeYT', metavar='ELBPTYPE', type=str, choices=elbptype, default='regular',
                        dest='elbptypeYT',
                        help='Choose the type of extended LBP features to compute in the YT plane (defaults to "%(default)s"). Allowed values are: ' + str(
                            elbptype))

    parser.add_argument('-cXY', '--circularXY', action='store_true', default=False, dest='cXY',
                        help='Is circular neighborhood in XY plane?  (defaults to "%(default)s")')
    parser.add_argument('-cXT', '--circularXT', action='store_true', default=False, dest='cXT',
                        help='Is circular neighborhood in XT plane?  (defaults to "%(default)s")')
    parser.add_argument('-cYT', '--circularYT', action='store_true', default=False, dest='cYT',
                        help='Is circular neighborhood in YT plane?  (defaults to "%(default)s")')

    parser.add_argument('-e', '--enrollment', action='store_true', default=False, dest='enrollment',
                        help='If True, will do the processing of the enrollment data of the database (defaults to "%(default)s")')

    parser.add_argument('-p', '--all-planes', action='store_true', default=False, dest='all_planes',
                        help='Save 5 planes in different files (XY, XT, YT, XY-YT, XY-XT-YT), otherwise will save only the XY-XT-YT (defaults to "%(default)s")')

    parser.add_argument('--bbx', '--boundingbox', action='store_true', default=False, dest='boundingbox',
                        help='If True, will read the face locations using the bbx function of the File class of the database. If False, will use faceloc.read_face utility to read the faceloc. For MSU-MFSD only (defaults to "%(default)s")')
    parser.add_argument('--nn', '--nonorm', dest='nonorm', action='store_true', default=False,
                        help='If True, normalization on the bounding box will NOT be perfomed. If False, normalization will be done depending on the -n parameter.')

    # For SGE grid processing @ Idiap
    parser.add_argument('--grid', dest='grid', action='store_true', default=False, help=argparse.SUPPRESS)

    # The next option just returns the total number of cases we will be running
    # It can be used to set jman --array option. To avoid user confusion, this
    # option is suppressed # from the --help menu
    parser.add_argument('--grid-count', dest='grid_count', action='store_true', default=False, help=argparse.SUPPRESS)

    #######
    # Database especific configuration
    #######
    # Database.create_parser(parser)
    Database.create_parser(parser, implements_any_of='video')

    args = parser.parse_args()

    lbphistlength = {'regular': 256, 'riu2': 10, 'uniform': 59}  # hardcoding the number of bins for the LBP variants

    inputDir = args.input_dir
    directory = args.output_dir

    if args.nonorm == True:  # the frames should not be normalized
        normfacesize = None
    elif len(args.normfacesize) == 1:  # just one values is given
        normfacesize = [args.normfacesize[0], args.normfacesize[0]]
    else:
        normfacesize = args.normfacesize

    facesize_filter = args.facesize_filter

    nXY = args.nXY
    nXT = args.nXT
    nYT = args.nYT

    rX = args.rX
    rY = args.rY
    rT = args.rT

    cXY = args.cXY
    cXT = args.cXT
    cYT = args.cYT

    lbptypeXY = args.lbptypeXY
    lbptypeXT = args.lbptypeXT
    lbptypeYT = args.lbptypeYT

    elbptypeXY = args.elbptypeXY
    elbptypeXT = args.elbptypeXT
    elbptypeYT = args.elbptypeYT

    tan_triggs = args.tan_triggs

    all_planes = args.all_planes

    # maxRadius = max(rX,rY,max(rT)) #Getting the max radius to extract the volume for analysis
    maxRadius = max(rT)  # Getting the max radius to extract the volume for analysis

    ########################
    # Querying the database
    ########################
    database = args.cls(args)

    if args.enrollment:
        process = database.get_enroll_data()
    else:
        realObjects, attackObjects = database.get_all_data()
        process = realObjects + attackObjects

    if args.grid_count:
        print len(process)
        sys.exit(0)

    # finally, if we are on a grid environment, just find what I have to process.
    if args.grid:
        key = int(os.environ['SGE_TASK_ID']) - 1
        if key >= len(process):
            raise RuntimeError, "Grid request for job %d on a setup with %d jobs" % \
                                (key, len(process))
        process = [process[key]]

    # Instancianting the Tan & Triggs algorithm (The default configurations only)
    tantriggs = bob.ip.base.TanTriggs()

    # processing each video
    for index, obj in enumerate(process):

        # Loading the file
        filename = str(obj.videofile(inputDir))
        # Loading the video
        input = bob.io.video.reader(filename)

        # Loading the face locations
        if string.find(database.short_description(), "CASIA") != -1:
            flocfile = obj.facefile()
            locations = preprocess_detections(flocfile, input.number_of_frames, facesize_filter=facesize_filter)
        elif string.find(database.short_description(), "MSU") != -1:
            if args.boundingbox:  # load the locations based on the bbx function of the File object
                locations = obj.bbx(directory=args.input_dir)
                locations = {x[0]: faceloc.BoundingBox(x[1], x[2], x[3], x[4]) for x in locations}  # for MSU MFSD
                locations = faceloc.expand_detections(locations, input.number_of_frames)
            else:
                facefile = obj.facefile(args.input_dir)
                locations = preprocess_detections(facefile, len(input), facesize_filter=args.min_face_size)
        else:
            flocfile = obj.facefile(args.input_dir)
            locations = preprocess_detections(flocfile, input.number_of_frames, facesize_filter=facesize_filter)

        sys.stdout.write("Processing file %s (%d frames) [%d/%d] " % (filename,
                                                                      input.number_of_frames, index + 1, len(process)))
        sys.stdout.flush()

        # start the work here...
        vin = input.load()  # load the video

        nFrames = vin.shape[0]
        # Converting all frames to grayscale
        grayFrames = numpy.zeros(shape=(nFrames, vin.shape[2], vin.shape[3]), dtype="uint8")
        for i in range(nFrames):
            grayFrames[i] = bob.ip.color.rgb_to_gray(vin[i, :, :, :])
            if string.find(database.short_description(),
                           "MSU") != -1 and obj.is_rotated():  # rotate the frame by 180 degrees if needed
                grayFrames[i] = numpy.rot90(numpy.rot90(grayFrames[i]))
            if (tan_triggs):
                grayFrames = grayFrames.astype("float64")
                grayFrames[i] = tantriggs(grayFrames[i])

        del vin

        ### STARTING the video analysis
        # Analysing each sub-volume in the video
        n_histograms = nFrames - 2 * maxRadius
        histVolumeXY = numpy.zeros(shape=(n_histograms, lbphistlength[lbptypeXY]))
        histVolumeXT = numpy.zeros(shape=(n_histograms, lbphistlength[lbptypeXT]))
        histVolumeYT = numpy.zeros(shape=(n_histograms, lbphistlength[lbptypeYT]))

        for i in range(maxRadius, nFrames - maxRadius):
            histLocalVolumeXY = None
            histLocalVolumeXT = None
            histLocalVolumeYT = None

            # For each different radius
            for r in rT:
                # The max local radius to select the volume
                maxLocalRadius = max(rX, rY, r)

                # Select the volume to analyse
                rangeValues = range(i - maxLocalRadius, i + 1 + maxLocalRadius)
                normalizedVolume = spoof.getNormFacesFromRange(grayFrames, rangeValues, locations, normfacesize)

                # Calculating the histograms
                histXY, histXT, histYT = spoof.lbptophist(normalizedVolume, nXY, nXT, nYT, rX, rY, r, cXY, cXT, cYT,
                                                          lbptypeXY, lbptypeXT, lbptypeYT, elbptypeXY, elbptypeXT,
                                                          elbptypeYT)

                # Concatenating in columns
                if histLocalVolumeXY is None:
                    histLocalVolumeXY = histXY
                    histLocalVolumeXT = histXT
                    histLocalVolumeYT = histYT
                else:
                    # Is no necessary concatenate more elements in space with diferent radius in type
                    histLocalVolumeXT = numpy.concatenate((histLocalVolumeXT, histXT), axis=1)
                    histLocalVolumeYT = numpy.concatenate((histLocalVolumeYT, histYT), axis=1)

            # Concatenating in rows
            histVolumeXY[i - maxRadius, :] = histLocalVolumeXY
            histVolumeXT[i - maxRadius, :] = histLocalVolumeXT
            histVolumeYT[i - maxRadius, :] = histLocalVolumeYT

        # In the LBP we lose the R_t first and R_t last frames. For that reason,
        # we need to add nan first and last R_t frames

        maxrT = max(rT)
        nanParametersXY = numpy.ones(shape=(maxrT, histVolumeXY.shape[1])) * numpy.NaN
        nanParametersXT = numpy.ones(shape=(maxrT, histVolumeXT.shape[1])) * numpy.NaN
        nanParametersYT = numpy.ones(shape=(maxrT, histVolumeYT.shape[1])) * numpy.NaN

        # Add in the first R_t frames
        histVolumeXY = numpy.concatenate((nanParametersXY, histVolumeXY), axis=0)
        histVolumeXT = numpy.concatenate((nanParametersXT, histVolumeXT), axis=0)
        histVolumeYT = numpy.concatenate((nanParametersYT, histVolumeYT), axis=0)

        # Add in the last R_t frames
        histVolumeXY = numpy.concatenate((histVolumeXY, nanParametersXY), axis=0)
        histVolumeXT = numpy.concatenate((histVolumeXT, nanParametersXT), axis=0)
        histVolumeYT = numpy.concatenate((histVolumeYT, nanParametersYT), axis=0)

        sys.stdout.write('\n')
        sys.stdout.flush()
        import ipdb; ipdb.set_trace();

        if (all_planes):
            obj.save(histVolumeXY, directory=os.path.join(directory, 'XY'), extension='.hdf5')
            obj.save(histVolumeXT, directory=os.path.join(directory, 'XT'), extension='.hdf5')
            obj.save(histVolumeYT, directory=os.path.join(directory, 'YT'), extension='.hdf5')

            histVolumeXT_YT = numpy.hstack((histVolumeXT, histVolumeYT))
            obj.save(histVolumeXT_YT, directory=os.path.join(directory, 'XT_YT'), extension='.hdf5')

            histVolumeXY_XT_YT = numpy.hstack((histVolumeXY, histVolumeXT, histVolumeYT))
            obj.save(histVolumeXY_XT_YT, directory=os.path.join(directory, 'XY_XT_YT'), extension='.hdf5')
        else:
            histVolumeXY_XT_YT = numpy.hstack((histVolumeXY, histVolumeXT, histVolumeYT))
            obj.save(histVolumeXY_XT_YT, directory=directory, extension='.hdf5')

    return 0


if __name__ == "__main__":
    main()
