"""
Module that contains the ARCSILandsat7Sensor class.
"""
############################################################################
#  arcsisensorlandsat.py
#
#  Copyright 2013 ARCSI.
#
#  ARCSI: 'Atmospheric and Radiometric Correction of Satellite Imagery'
#
#  ARCSI is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  ARCSI is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with ARCSI.  If not, see <http://www.gnu.org/licenses/>.
#
#
# Purpose:  A class for read the landsat sensor header file and applying
#           the pre-processing operations within ARCSI to the landsat 7
#           datasets.
#
# Author: Pete Bunting
# Email: pfb@aber.ac.uk
# Date: 05/07/2013
# Version: 1.0
#
# History:
# Version 1.0 - Created.
#
############################################################################

# Import updated print function into python 2.7
from __future__ import print_function
# Import updated division operator into python 2.7
from __future__ import division
# import abstract base class stuff
from .arcsisensor import ARCSIAbstractSensor
# Import the ARCSI exception class
from .arcsiexception import ARCSIException
# Import the ARCSI utilities class
from .arcsiutils import ARCSIUtils
# Import the ARCSI landsat utilities class
from .arcsiutils import ARCSILandsatMetaUtils
# Import the datetime module
import datetime
# Import the GDAL/OGR spatial reference library
from osgeo import osr
from osgeo import ogr
# Import OS path module for manipulating the file system
import os.path
# Import the sys module
import sys
# Import the RSGISLib Image Calibration Module.
import rsgislib.imagecalibration
# Import the RSGISLib Image Utilities Module.
import rsgislib.imageutils
# Import the collections module
import collections
# Import the py6s module for running 6S from python.
import Py6S
# Import the python maths library
import math
# Import the RIOS RAT library
from rios import rat
# Import the GDAL python library
import osgeo.gdal as gdal
# Import the scipy optimisation library - used for finding AOD values form the imagery.
from scipy.optimize import minimize
# Import the numpy module
import numpy
# Import the glob module
import glob
# Import the subprocess module
import subprocess
# Import JSON module
import json
# Import the shutil module
import shutil
# Import the solar angle tools from RSGISLib
import rsgislib.imagecalibration.solarangles
# Using python-fmask (http://pythonfmask.org)
import fmask.landsatangles
import fmask.config
import fmask.fmask
import rios.fileinfo
import rsgislib.segmentation
import rsgislib.segmentation.segutils

class ARCSILandsat7Sensor (ARCSIAbstractSensor):
    """
    A class which represents the landsat 7 sensor to read
    header parameters and apply data processing operations.
    """
    def __init__(self, debugMode, inputImage):
        ARCSIAbstractSensor.__init__(self, debugMode, inputImage)
        self.sensor = "LS7"
        self.band1File = ""
        self.band2File = ""
        self.band3File = ""
        self.band4File = ""
        self.band5File = ""
        self.band6aFile = ""
        self.band6bFile = ""
        self.band7File = ""
        self.bandPanFile = ""
        self.bandQAFile = ""
        self.row = 0
        self.path = 0

        self.b1CalMin = 0
        self.b1CalMax = 0
        self.b2CalMin = 0
        self.b2CalMax = 0
        self.b3CalMin = 0
        self.b3CalMax = 0
        self.b4CalMin = 0
        self.b4CalMax = 0
        self.b5CalMin = 0
        self.b5CalMax = 0
        self.b6aCalMin = 0
        self.b6aCalMax = 0
        self.b6bCalMin = 0
        self.b6bCalMax = 0
        self.b7CalMin = 0
        self.b7CalMax = 0
        self.b8CalMin = 0
        self.b8CalMax = 0

        self.b1MinRad = 0.0
        self.b1MaxRad = 0.0
        self.b2MinRad = 0.0
        self.b2MaxRad = 0.0
        self.b3MinRad = 0.0
        self.b3MaxRad = 0.0
        self.b4MinRad = 0.0
        self.b4MaxRad = 0.0
        self.b5MinRad = 0.0
        self.b5MaxRad = 0.0
        self.b6aMinRad = 0.0
        self.b6aMaxRad = 0.0
        self.b6bMinRad = 0.0
        self.b6bMaxRad = 0.0
        self.b7MinRad = 0.0
        self.b7MaxRad = 0.0
        self.b8MinRad = 0.0
        self.b8MaxRad = 0.0

        self.sensorID = ""
        self.spacecraftID = ""
        self.cloudCover = 0.0
        self.cloudCoverLand = 0.0
        self.earthSunDistance = 0.0
        self.gridCellSizePan = 0.0
        self.gridCellSizeRefl = 0.0
        self.gridCellSizeTherm = 0.0

    def extractHeaderParameters(self, inputHeader, wktStr):
        """
        Understands and parses the Landsat MTL header files
        """
        try:
            if not self.userSpInputImage is None:
                raise ARCSIException("Landsat sensor cannot accept a user specified image file - only the images in the header file will be used.")
            self.headerFileName = os.path.split(inputHeader)[1]
            
            arcsiUtils = ARCSIUtils()

            print("Reading header file")
            hFile = open(inputHeader, 'r')
            headerParams = dict()
            for line in hFile:
                line = line.strip()
                if line:
                    lineVals = line.split('=')
                    if len(lineVals) == 2:
                        if (lineVals[0].strip() != "GROUP") or (lineVals[0].strip() != "END_GROUP"):
                            headerParams[lineVals[0].strip()] = lineVals[1].strip().replace('"','')
            hFile.close()
            print("Extracting Header Values")
            # Get the sensor info.
            if ((headerParams["SPACECRAFT_ID"].upper() == "LANDSAT_7") or (headerParams["SPACECRAFT_ID"].upper() == "LANDSAT7")) and ((headerParams["SENSOR_ID"].upper() == "ETM") or (headerParams["SENSOR_ID"].upper() == "ETM+")):
                self.sensor = "LS7"
            else:
                raise ARCSIException("Do no recognise the spacecraft and sensor or combination.")

            self.sensorID = headerParams["SENSOR_ID"]
            self.spacecraftID = headerParams["SPACECRAFT_ID"]

            # Get row/path
            try:
                self.row = int(headerParams["WRS_ROW"])
            except KeyError:
                self.row = int(headerParams["STARTING_ROW"])
            self.path = int(headerParams["WRS_PATH"])

            # Get date and time of the acquisition
            try:
                acData = headerParams["DATE_ACQUIRED"].split('-')
            except KeyError:
                acData = headerParams["ACQUISITION_DATE"].split('-')
            try:
                acTime = headerParams["SCENE_CENTER_TIME"].split(':')
            except KeyError:
                acTime = headerParams["SCENE_CENTER_SCAN_TIME"].split(':')
            secsTime = acTime[2].split('.')
            self.acquisitionTime = datetime.datetime(int(acData[0]), int(acData[1]), int(acData[2]), int(acTime[0]), int(acTime[1]), int(secsTime[0]))

            self.solarZenith = 90-arcsiUtils.str2Float(headerParams["SUN_ELEVATION"])
            self.solarAzimuth = arcsiUtils.str2Float(headerParams["SUN_AZIMUTH"])

            # Get the geographic lat/long corners of the image.
            geoCorners = ARCSILandsatMetaUtils.getGeographicCorners(headerParams)

            self.latTL = geoCorners[0]
            self.lonTL = geoCorners[1]
            self.latTR = geoCorners[2]
            self.lonTR = geoCorners[3]
            self.latBL = geoCorners[4]
            self.lonBL = geoCorners[5]
            self.latBR = geoCorners[6]
            self.lonBR = geoCorners[7]

            # Get the projected X/Y corners of the image
            projectedCorners = ARCSILandsatMetaUtils.getProjectedCorners(headerParams)

            self.xTL = projectedCorners[0]
            self.yTL = projectedCorners[1]
            self.xTR = projectedCorners[2]
            self.yTR = projectedCorners[3]
            self.xBL = projectedCorners[4]
            self.yBL = projectedCorners[5]
            self.xBR = projectedCorners[6]
            self.yBR = projectedCorners[7]

            # Get projection
            inProj = osr.SpatialReference()
            if (headerParams["MAP_PROJECTION"] == "UTM"):
                try:
                    datum = headerParams["DATUM"]
                    if datum != "WGS84":
                        raise ARCSIException("Datum not recogised. Expected 'WGS84' got '{}'".format(datum))
                except KeyError:
                    pass
                try:
                    ellipsoid = headerParams["ELLIPSOID"]
                    if ellipsoid != "WGS84":
                        raise ARCSIException("Ellipsoid not recogised. Expected 'WGS84' got '{}'".format(ellipsoid))
                except KeyError:
                    pass
                try:
                    utmZone = int(headerParams["UTM_ZONE"])
                except KeyError:
                    utmZone = int(headerParams["ZONE_NUMBER"])
                # FIXME: should this be hardcoded to north?
                utmCode = "WGS84UTM" + str(utmZone) + str("N")
                #print("UTM: ", utmCode)
                inProj.ImportFromEPSG(self.epsgCodes[utmCode])
            elif (headerParams["MAP_PROJECTION"] == "PS") and (headerParams["DATUM"] == "WGS84") and (headerParams["ELLIPSOID"] == "WGS84"):
                inProj.ImportFromWkt("PROJCS[\"PS WGS84\", GEOGCS[\"WGS 84\",DATUM[\"WGS_1984\",SPHEROID[\"WGS 84\",6378137,298.257223563, AUTHORITY[\"EPSG\",\"7030\"]],AUTHORITY[\"EPSG\",\"6326\"]],PRIMEM[\"Greenwich\",0],UNIT[\"degree\",0.0174532925199433],AUTHORITY[\"EPSG\",\"4326\"]],PROJECTION[\"Polar_Stereographic\"],PARAMETER[\"latitude_of_origin\",-71],PARAMETER[\"central_meridian\",0],PARAMETER[\"scale_factor\",1],PARAMETER[\"false_easting\",0],PARAMETER[\"false_northing\",0],UNIT[\"metre\",1,AUTHORITY[\"EPSG\",\"9001\"]]]")
            else:
                raise ARCSIException("Expecting Landsat to be projected in UTM or PolarStereographic (PS) with datum=WGS84 and ellipsoid=WGS84.")

            if self.inWKT is "":
                self.inWKT = inProj.ExportToWkt()

            # Check image is square!
            if not ((self.xTL == self.xBL) and (self.yTL == self.yTR) and (self.xTR == self.xBR) and (self.yBL == self.yBR)):
                raise ARCSIException("Image is not square in projected coordinates.")

            self.xCentre = self.xTL + ((self.xTR - self.xTL)/2)
            self.yCentre = self.yBR + ((self.yTL - self.yBR)/2)

            self.lonCentre, self.latCentre = arcsiUtils.getLongLat(inProj, self.xCentre, self.yCentre)

            #print("Lat: " + str(self.latCentre) + " Long: " + str(self.lonCentre))

            metaFilenames = ARCSILandsatMetaUtils.getBandFilenames(headerParams, 8)

            filesDIR = os.path.dirname(inputHeader)

            self.band1File = os.path.join(filesDIR, metaFilenames[0])
            self.band2File = os.path.join(filesDIR, metaFilenames[1])
            self.band3File = os.path.join(filesDIR, metaFilenames[2])
            self.band4File = os.path.join(filesDIR, metaFilenames[3])
            self.band5File = os.path.join(filesDIR, metaFilenames[4])
            self.band7File = os.path.join(filesDIR, metaFilenames[6])
            self.bandPanFile = os.path.join(filesDIR, metaFilenames[7])

            try:
                self.bandQAFile = os.path.join(filesDIR, headerParams["FILE_NAME_QUALITY_L1_PIXEL"])
            except KeyError:
                try:
                    self.bandQAFile = os.path.join(filesDIR, headerParams["FILE_NAME_BAND_QUALITY"])
                except KeyError:
                    print("Warning - the quality band is not available. Pre-collection 1 data unsupported.")
                    self.bandQAFile = ""

            try:
                self.band6aFile = os.path.join(filesDIR,headerParams["FILE_NAME_BAND_6_VCID_1"])
            except KeyError:
                self.band6aFile = os.path.join(filesDIR,headerParams["BAND61_FILE_NAME"])
            try:
                self.band6bFile = os.path.join(filesDIR,headerParams["FILE_NAME_BAND_6_VCID_2"])
            except KeyError:
                self.band6bFile = os.path.join(filesDIR,headerParams["BAND62_FILE_NAME"])

            bands_list = ["1","2","3","4","5","6_VCID_1","6_VCID_2","7","8"]

            metaQCalMinList = {}
            metaQCalMaxList = {}

            for band_num in bands_list:
                try:
                    metaQCalMinList[band_num] = arcsiUtils.str2Float(headerParams["QUANTIZE_CAL_MIN_BAND_{}".format(band_num)], 1.0)
                    metaQCalMaxList[band_num] = arcsiUtils.str2Float(headerParams["QUANTIZE_CAL_MAX_BAND_{}".format(band_num)], 255.0)
                except KeyError:
                    if band_num == "6_VCID_1":
                        metaQCalMinList[band_num] = arcsiUtils.str2Float(headerParams["QCALMIN_BAND61"], 1.0)
                        metaQCalMaxList[band_num] = arcsiUtils.str2Float(headerParams["QCALMAX_BAND61"], 255.0)
                    elif band_num == "6_VCID_2":
                        metaQCalMinList[band_num] = arcsiUtils.str2Float(headerParams["QCALMIN_BAND62"], 1.0)
                        metaQCalMaxList[band_num] = arcsiUtils.str2Float(headerParams["QCALMAX_BAND62"], 255.0)
                    else:
                        metaQCalMinList[band_num] = arcsiUtils.str2Float(headerParams["QCALMIN_BAND{}".format(band_num)], 1.0)
                        metaQCalMaxList[band_num] = arcsiUtils.str2Float(headerParams["QCALMAX_BAND{}".format(band_num)], 255.0)

            self.b1CalMin = metaQCalMinList["1"]
            self.b1CalMax = metaQCalMaxList["1"]
            self.b2CalMin = metaQCalMinList["2"]
            self.b2CalMax = metaQCalMaxList["2"]
            self.b3CalMin = metaQCalMinList["3"]
            self.b3CalMax = metaQCalMaxList["3"]
            self.b4CalMin = metaQCalMinList["4"]
            self.b4CalMax = metaQCalMaxList["4"]
            self.b5CalMin = metaQCalMinList["5"]
            self.b5CalMax = metaQCalMaxList["5"]
            self.b6aCalMin = metaQCalMinList["6_VCID_1"]
            self.b6aCalMax = metaQCalMaxList["6_VCID_1"]
            self.b6bCalMin = metaQCalMinList["6_VCID_2"]
            self.b6bCalMax = metaQCalMaxList["6_VCID_2"]
            self.b7CalMin = metaQCalMinList["7"]
            self.b7CalMax = metaQCalMaxList["7"]
            self.b8CalMin = metaQCalMinList["8"]
            self.b8CalMax = metaQCalMaxList["8"]

            lMin = [-6.200, -6.400, -5.000, -5.100, -1.000, 0.000, 3.200, -0.350, -4.700]
            lMax = [191.600, 196.500, 152.900, 241.100, 31.060, 17.040, 12.650, 10.800, 243.100]

            metaRadMinList = {}
            metaRadMaxList = {}

            #for band_num in bands_list:
            for i in range(0,9):
                band_num = bands_list[i]
                try:
                    metaRadMinList[band_num] = arcsiUtils.str2Float(headerParams["RADIANCE_MINIMUM_BAND_{}".format(band_num)], lMin[i])
                    metaRadMaxList[band_num] = arcsiUtils.str2Float(headerParams["RADIANCE_MAXIMUM_BAND_{}".format(band_num)], lMax[i])
                except KeyError:
                    if band_num == "6_VCID_1":
                        metaRadMinList[band_num] = arcsiUtils.str2Float(headerParams["LMIN_BAND61"], lMin[i])
                        metaRadMaxList[band_num] = arcsiUtils.str2Float(headerParams["LMAX_BAND61"], lMax[i])
                    elif band_num == "6_VCID_2":
                        metaRadMinList[band_num] = arcsiUtils.str2Float(headerParams["LMIN_BAND62"], lMin[i])
                        metaRadMaxList[band_num] = arcsiUtils.str2Float(headerParams["LMAX_BAND62"], lMax[i])
                    else:
                        metaRadMinList[band_num] = arcsiUtils.str2Float(headerParams["LMIN_BAND{}".format(band_num)], lMin[i])
                        metaRadMaxList[band_num] = arcsiUtils.str2Float(headerParams["LMAX_BAND{}".format(band_num)], lMax[i])

            self.b1MinRad = metaRadMinList["1"]
            self.b1MaxRad = metaRadMaxList["1"]
            self.b2MinRad = metaRadMinList["2"]
            self.b2MaxRad = metaRadMaxList["2"]
            self.b3MinRad = metaRadMinList["3"]
            self.b3MaxRad = metaRadMaxList["3"]
            self.b4MinRad = metaRadMinList["4"]
            self.b4MaxRad = metaRadMaxList["4"]
            self.b5MinRad = metaRadMinList["5"]
            self.b5MaxRad = metaRadMaxList["5"]
            self.b6aMinRad = metaRadMinList["6_VCID_1"]
            self.b6aMaxRad = metaRadMaxList["6_VCID_1"]
            self.b6bMinRad = metaRadMinList["6_VCID_2"]
            self.b6bMaxRad = metaRadMaxList["6_VCID_2"]
            self.b7MinRad = metaRadMinList["7"]
            self.b7MaxRad = metaRadMaxList["7"]
            self.b8MinRad = metaRadMinList["8"]
            self.b8MaxRad = metaRadMaxList["8"]

            if "CLOUD_COVER" in headerParams:
                self.cloudCover = arcsiUtils.str2Float(headerParams["CLOUD_COVER"], 0.0)
            if "CLOUD_COVER_LAND" in headerParams:
                self.cloudCoverLand = arcsiUtils.str2Float(headerParams["CLOUD_COVER_LAND"], 0.0)
            if "EARTH_SUN_DISTANCE" in headerParams:
                self.earthSunDistance = arcsiUtils.str2Float(headerParams["EARTH_SUN_DISTANCE"], 0.0)
            if "GRID_CELL_SIZE_REFLECTIVE" in headerParams:
                self.gridCellSizeRefl = arcsiUtils.str2Float(headerParams["GRID_CELL_SIZE_REFLECTIVE"], 60.0)
            if "GRID_CELL_SIZE_THERMAL" in headerParams:
                self.gridCellSizeTherm = arcsiUtils.str2Float(headerParams["GRID_CELL_SIZE_THERMAL"], 30.0)
            if "GRID_CELL_SIZE_PANCHROMATIC" in headerParams:
                self.gridCellSizePan = arcsiUtils.str2Float(headerParams["GRID_CELL_SIZE_PANCHROMATIC"], 15.0)

            self.hasImageDataMask = True

            # Read MTL header into python dict for python-fmask
            self.fmaskMTLInfo = fmask.config.readMTLFile(inputHeader)

            fileDateStr = f"{headerParams['DATE_ACQUIRED'].strip()}T{headerParams['SCENE_CENTER_TIME'].split('.')[0]}"
            self.fileDateObj = datetime.datetime.strptime(fileDateStr, "%Y-%m-%dT%H:%M:%S")

        except Exception as e:
            raise e

    def getSolarIrrStdSolarGeom(self):
        """
        Get Solar Azimuth and Zenith as standard geometry.
        Azimuth: N=0, E=90, S=180, W=270.
        """
        solarAz = rsgislib.imagecalibration.solarangles.getSolarIrrConventionSolarAzimuthFromUSGS(self.solarAzimuth)
        return (solarAz, self.solarZenith)

    def getSensorViewGeom(self):
        """
        Get sensor viewing angles
        returns (viewAzimuth, viewZenith)
        """
        return (0.0, 0.0)

    def generateOutputBaseName(self):
        """
        Provides an implementation for the landsat sensor
        """
        rowpath = "r" + str(self.row) + "p" + str(self.path)
        outname = self.defaultGenBaseOutFileName()
        outname = outname + str("_") + rowpath
        return outname

    def generateMetaDataFile(self, outputPath, outputFileName, productsStr, validMaskImage="", footprintCalc=False, calcdValuesDict=dict(), outFilesDict=dict()):
        """
        Generate file metadata.
        """
        outJSONFilePath = os.path.join(outputPath, outputFileName)
        jsonData = self.getJSONDictDefaultMetaData(productsStr, validMaskImage, footprintCalc, calcdValuesDict, outFilesDict)
        sensorInfo = jsonData['SensorInfo']
        sensorInfo['Row'] = self.row
        sensorInfo['Path'] = self.path
        sensorInfo['SensorID'] = self.sensorID
        sensorInfo['SpacecraftID'] = self.spacecraftID
        acqDict = jsonData['AcquasitionInfo']
        acqDict['EarthSunDistance'] = self.earthSunDistance
        imgInfo = dict()
        imgInfo['CloudCover'] = self.cloudCover
        imgInfo['CloudCoverLand'] = self.cloudCoverLand
        imgInfo['CellSizePan'] = self.gridCellSizePan
        imgInfo['CellSizeRefl'] = self.gridCellSizeRefl
        imgInfo['CellSizeTherm'] = self.gridCellSizeTherm
        jsonData['ImageInfo'] = imgInfo

        with open(outJSONFilePath, 'w') as outfile:
            json.dump(jsonData, outfile, sort_keys=True,indent=4, separators=(',', ': '), ensure_ascii=False)

    def hasThermal(self):
        return True

    def maskInputImages(self):
        return self.hasImageDataMask

    def applyImageDataMask(self, inputHeader, inputImage, outputPath, outputMaskName, outputImgName, outFormat, outWKTFile):
        print("Apply Input Image Mask to Input Image File")
        rsgisUtils = rsgislib.RSGISPyUtils()
        outputImage = os.path.join(outputPath, outputImgName)
        outputMaskImage = os.path.join(outputPath, outputMaskName)
        dataDIR = os.path.split(inputHeader)[0]
        maskDIR = os.path.join(dataDIR, "gap_mask")

        if os.path.exists(maskDIR) and os.path.isdir(maskDIR):
            maskList = glob.glob(os.path.join(maskDIR, "*.TIF.gz"))
            if len(maskList) > 0:
               for file in maskList:
                    cmd = "gzip -d " + file
                    subprocess.call(cmd, shell=True)

            maskList = glob.glob(os.path.join(maskDIR, "*.TIF"))
            if not len(maskList) > 0:
                raise Exception("Could not find mask files.")

            stackImageMasks = []
            bandImgIDs = ['GM_B1', 'GM_B2', 'GM_B3', 'GM_B4', 'GM_B5', 'GM_B7']
            bandImgIDs2 = ['B1', 'B2', 'B3', 'B4', 'B5', 'B7']
            for bandIDIdx in range(len(bandImgIDs)):
                for imgMask in maskList:
                    if (bandImgIDs[bandIDIdx] in imgMask) or (bandImgIDs2[bandIDIdx] in imgMask):
                        stackImageMasks.append(rsgislib.imagecalc.BandDefn(bandImgIDs[bandIDIdx], imgMask, 1))
                        break

            if not(len(stackImageMasks) == rsgisUtils.getImageBandCount(inputImage)):
                raise ARCSIException('Could not find image masks for all the input image bands')
    
            outputMaskImageInit = outputMaskImage
            if not outWKTFile is None:
                outputMaskImageInit = os.path.join(outputPath, "InitMask_arcsi_" + outputMaskName)

            rsgislib.imagecalc.bandMath(outputMaskImageInit, "GM_B1*GM_B2*GM_B3*GM_B4*GM_B5*GM_B7", outFormat, rsgislib.TYPE_8UINT, stackImageMasks)

            if not outWKTFile is None:
                refImgDS = gdal.Open(inputImage, gdal.GA_ReadOnly)
                if refImgDS is None:
                    raise ARCSIException('Could not open the input image: ' + inputImage)
                geoTransform = refImgDS.GetGeoTransform()
                if geoTransform is None:
                    raise ARCSIException('Could read the geotransform from the input image: ' + inputImage)
                xPxlRes = geoTransform[1]
                yPxlRes = geoTransform[5]
                refImgDS = None
                cmd = 'gdalwarp -t_srs ' + outWKTFile + ' -tr ' + str(xPxlRes) + ' ' + str(yPxlRes) + ' -ot Byte -wt Float32 ' \
                    + '-r near -tap -srcnodata 0 -dstnodata 0 -of ' + outFormat + ' -overwrite ' \
                    + outputMaskImageInit + ' ' + outputMaskImage
                print(cmd)
                try:
                    subprocess.call(cmd, shell=True)
                except OSError as e:
                    raise ARCSIException('Could not re-projection image mask: ' + cmd)
                if not os.path.exists(outputMaskImage):
                    raise ARCSIException('Reprojected image mask is not present: ' + outputMaskImage)
                else:
                    rsgisUtils = rsgislib.RSGISPyUtils()
                    rsgisUtils.deleteFileWithBasename(outputMaskImageInit)
            else:
                outputMaskImage = outputMaskImageInit
            rsgislib.imageutils.maskImage(inputImage, outputMaskImage, outputImage, outFormat, rsgislib.TYPE_32FLOAT, 0, 0)
        else:
            print("\tThere is no mask to mask this scene...")
            outputImage = inputImage
            outputMaskImage = None
            self.hasImageDataMask = False
        return outputImage, outputMaskImage

    def expectedImageDataPresent(self):
        imageDataPresent = True

        if not os.path.exists(self.band1File):
            imageDataPresent = False
        if not os.path.exists(self.band2File):
            imageDataPresent = False
        if not os.path.exists(self.band3File):
            imageDataPresent = False
        if not os.path.exists(self.band4File):
            imageDataPresent = False
        if not os.path.exists(self.band5File):
            imageDataPresent = False
        if not os.path.exists(self.band6aFile):
            imageDataPresent = False
        if not os.path.exists(self.band6bFile):
            imageDataPresent = False
        if not os.path.exists(self.band7File):
            imageDataPresent = False

        return imageDataPresent

    def mosaicImageTiles(self, outputPath):
        raise ARCSIException("Image data does not need mosaicking")

    def resampleImgRes(self, outputPath, resampleToLowResImg, resampleMethod='cubic', multicore=False):
        raise ARCSIException("Image data does not need resampling")

    def sharpenLowResRadImgBands(self, inputImg, outputImage, outFormat):
        raise ARCSIException("Image sharpening is not available for this sensor.")

    def generateValidImageDataMask(self, outputPath, outputMaskName, viewAngleImg, outFormat):
        print("Create the valid data mask")
        tmpBaseName = os.path.splitext(outputMaskName)[0]
        tmpValidPxlMsk = os.path.join(outputPath, tmpBaseName+'vldpxlmsk.kea')
        outputImage = os.path.join(outputPath, outputMaskName)
        inImages = [self.band1File, self.band2File, self.band3File, self.band4File, self.band5File, self.band7File, self.band6aFile, self.band6bFile]
        rsgislib.imageutils.genValidMask(inimages=inImages, outimage=tmpValidPxlMsk, gdalformat='KEA', nodata=0.0)
        rsgislib.rastergis.populateStats(tmpValidPxlMsk, True, False, True)
        # Check there is valid data
        ratDS = gdal.Open(tmpValidPxlMsk, gdal.GA_ReadOnly)
        Histogram = rat.readColumn(ratDS, "Histogram")
        ratDS = None
        if Histogram.shape[0] < 2:
            raise ARCSIException("There is no valid data in this image.")
        if not os.path.exists(viewAngleImg):
            print("Calculate Image Angles.")
            imgInfo = rios.fileinfo.ImageInfo(tmpValidPxlMsk)
            corners = fmask.landsatangles.findImgCorners(tmpValidPxlMsk, imgInfo)
            nadirLine = fmask.landsatangles.findNadirLine(corners)
            extentSunAngles = fmask.landsatangles.sunAnglesForExtent(imgInfo, self.fmaskMTLInfo)
            satAzimuth = fmask.landsatangles.satAzLeftRight(nadirLine)
            fmask.landsatangles.makeAnglesImage(tmpValidPxlMsk, viewAngleImg, nadirLine, extentSunAngles, satAzimuth, imgInfo)
            dataset = gdal.Open(viewAngleImg, gdal.GA_Update)
            if not dataset is None:
                dataset.GetRasterBand(1).SetDescription("SatelliteAzimuth")
                dataset.GetRasterBand(2).SetDescription("SatelliteZenith")
                dataset.GetRasterBand(3).SetDescription("SolorAzimuth")
                dataset.GetRasterBand(4).SetDescription("SolorZenith")
            dataset = None
        rsgislib.imagecalc.bandMath(outputImage, '(VA<14)&&(VM==1)?1:0', outFormat, rsgislib.TYPE_8UINT, [rsgislib.imagecalc.BandDefn('VA', viewAngleImg, 2), rsgislib.imagecalc.BandDefn('VM', tmpValidPxlMsk, 1)])
        rsgisUtils = rsgislib.RSGISPyUtils()
        rsgisUtils.deleteFileWithBasename(tmpValidPxlMsk)
        return outputImage

    def convertImageToRadiance(self, outputPath, outputReflName, outputThermalName, outFormat):
        print("Converting to Radiance")
        outputReflImage = os.path.join(outputPath, outputReflName)
        outputThermalImage = None
        bandDefnSeq = list()

        lsBand = collections.namedtuple('LSBand', ['bandName', 'fileName', 'bandIndex', 'lMin', 'lMax', 'qCalMin', 'qCalMax'])
        bandDefnSeq.append(lsBand(bandName="Blue", fileName=self.band1File, bandIndex=1, lMin=self.b1MinRad, lMax=self.b1MaxRad, qCalMin=self.b1CalMin, qCalMax=self.b1CalMax))
        bandDefnSeq.append(lsBand(bandName="Green", fileName=self.band2File, bandIndex=1, lMin=self.b2MinRad, lMax=self.b2MaxRad, qCalMin=self.b2CalMin, qCalMax=self.b2CalMax))
        bandDefnSeq.append(lsBand(bandName="Red", fileName=self.band3File, bandIndex=1, lMin=self.b3MinRad, lMax=self.b3MaxRad, qCalMin=self.b3CalMin, qCalMax=self.b3CalMax))
        bandDefnSeq.append(lsBand(bandName="NIR", fileName=self.band4File, bandIndex=1, lMin=self.b4MinRad, lMax=self.b4MaxRad, qCalMin=self.b4CalMin, qCalMax=self.b4CalMax))
        bandDefnSeq.append(lsBand(bandName="SWIR1", fileName=self.band5File, bandIndex=1, lMin=self.b5MinRad, lMax=self.b5MaxRad, qCalMin=self.b5CalMin, qCalMax=self.b5CalMax))
        bandDefnSeq.append(lsBand(bandName="SWIR2", fileName=self.band7File, bandIndex=1, lMin=self.b7MinRad, lMax=self.b7MaxRad, qCalMin=self.b7CalMin, qCalMax=self.b7CalMax))
        rsgislib.imagecalibration.landsat2Radiance(outputReflImage, outFormat, bandDefnSeq)

        if not outputThermalName == None:
            outputThermalImage = os.path.join(outputPath, outputThermalName)
            bandDefnSeq = list()
            lsBand = collections.namedtuple('LSBand', ['bandName', 'fileName', 'bandIndex', 'lMin', 'lMax', 'qCalMin', 'qCalMax'])
            bandDefnSeq.append(lsBand(bandName="ThermalB6a", fileName=self.band6aFile, bandIndex=1, lMin=self.b6aMinRad, lMax=self.b6aMaxRad, qCalMin=self.b6aCalMin, qCalMax=self.b6aCalMax))
            bandDefnSeq.append(lsBand(bandName="ThermalB6b", fileName=self.band6bFile, bandIndex=1, lMin=self.b6bMinRad, lMax=self.b6bMaxRad, qCalMin=self.b6bCalMin, qCalMax=self.b6bCalMax))
            rsgislib.imagecalibration.landsat2Radiance(outputThermalImage, outFormat, bandDefnSeq)

        return outputReflImage, outputThermalImage

    def generateImageSaturationMask(self, outputPath, outputName, outFormat):
        print("Generate Saturation Image")
        outputImage = os.path.join(outputPath, outputName)

        lsBand = collections.namedtuple('LSBand', ['bandName', 'fileName', 'bandIndex', 'satVal'])
        bandDefnSeq = list()
        bandDefnSeq.append(lsBand(bandName="Blue", fileName=self.band1File, bandIndex=1, satVal=self.b1CalMax))
        bandDefnSeq.append(lsBand(bandName="Green", fileName=self.band2File, bandIndex=1, satVal=self.b2CalMax))
        bandDefnSeq.append(lsBand(bandName="Red", fileName=self.band3File, bandIndex=1, satVal=self.b3CalMax))
        bandDefnSeq.append(lsBand(bandName="NIR", fileName=self.band4File, bandIndex=1, satVal=self.b4CalMax))
        bandDefnSeq.append(lsBand(bandName="SWIR1", fileName=self.band5File, bandIndex=1, satVal=self.b5CalMax))
        bandDefnSeq.append(lsBand(bandName="SWIR2", fileName=self.band7File, bandIndex=1, satVal=self.b7CalMax))
        bandDefnSeq.append(lsBand(bandName="ThermalB6a", fileName=self.band6aFile, bandIndex=1, satVal=self.b6aCalMax))
        bandDefnSeq.append(lsBand(bandName="ThermalB6b", fileName=self.band6bFile, bandIndex=1, satVal=self.b6bCalMax))

        rsgislib.imagecalibration.saturatedPixelsMask(outputImage, outFormat, bandDefnSeq)

        return outputImage

    def convertThermalToBrightness(self, inputRadImage, outputPath, outputName, outFormat, scaleFactor):
        print("Converting to Thermal Brightness")
        outputThermalImage = os.path.join(outputPath, outputName)
        bandDefnSeq = list()

        lsBand = collections.namedtuple('LSBand', ['bandName', 'bandIndex', 'k1', 'k2'])
        bandDefnSeq.append(lsBand(bandName="ThermalB6a", bandIndex=1, k1=666.09, k2=1282.71))
        bandDefnSeq.append(lsBand(bandName="ThermalB6b", bandIndex=2, k1=666.09, k2=1282.71))
        rsgislib.imagecalibration.landsatThermalRad2Brightness(inputRadImage, outputThermalImage, outFormat, rsgislib.TYPE_32INT, scaleFactor, bandDefnSeq)
        return outputThermalImage

    def convertImageToTOARefl(self, inputRadImage, outputPath, outputName, outFormat, scaleFactor):
        print("Converting to TOA")
        outputImage = os.path.join(outputPath, outputName)
        solarIrradianceVals = list()
        IrrVal = collections.namedtuple('SolarIrradiance', ['irradiance'])
        solarIrradianceVals.append(IrrVal(irradiance=1997.0))
        solarIrradianceVals.append(IrrVal(irradiance=1812.0))
        solarIrradianceVals.append(IrrVal(irradiance=1533.0))
        solarIrradianceVals.append(IrrVal(irradiance=1039.0))
        solarIrradianceVals.append(IrrVal(irradiance=230.8))
        solarIrradianceVals.append(IrrVal(irradiance=84.9))
        rsgislib.imagecalibration.radiance2TOARefl(inputRadImage, outputImage, outFormat, rsgislib.TYPE_16UINT, scaleFactor, self.acquisitionTime.year, self.acquisitionTime.month, self.acquisitionTime.day, self.solarZenith, solarIrradianceVals)
        return outputImage

    def generateCloudMask(self, inputReflImage, inputSatImage, inputThermalImage, inputViewAngleImg, inputValidImg, outputPath, outputName, outFormat, tmpPath, scaleFactor, cloud_msk_methods=None):
        try:
            arcsiUtils = ARCSIUtils()
            rsgisUtils = rsgislib.RSGISPyUtils()
            outputImage = os.path.join(outputPath, outputName)
            tmpBaseName = os.path.splitext(outputName)[0]
            imgExtension = arcsiUtils.getFileExtension(outFormat)
            tmpBaseDIR = os.path.join(tmpPath, tmpBaseName)

            tmpDIRExisted = True
            if not os.path.exists(tmpBaseDIR):
                os.makedirs(tmpBaseDIR)
                tmpDIRExisted = False

            if (cloud_msk_methods is None) or (cloud_msk_methods == 'FMASK'):
                tmpFMaskOut = os.path.join(tmpBaseDIR, tmpBaseName + '_pyfmaskout.kea')

                tmpThermalLayer = self.band6aFile
                if not rsgisUtils.doGDALLayersHaveSameProj(inputThermalImage, self.band6aFile):
                    tmpThermalLayer = os.path.join(tmpBaseDIR, tmpBaseName+'_thermalresample.kea')
                    rsgislib.imageutils.resampleImage2Match(inputThermalImage, self.band6aFile, tmpThermalLayer, 'KEA', 'cubic', rsgislib.TYPE_32FLOAT)

                minCloudSize = 0
                cloudBufferDistance = 150
                shadowBufferDistance = 300

                fmaskFilenames = fmask.config.FmaskFilenames()
                fmaskFilenames.setTOAReflectanceFile(inputReflImage)
                fmaskFilenames.setThermalFile(tmpThermalLayer)
                fmaskFilenames.setSaturationMask(inputSatImage)
                fmaskFilenames.setOutputCloudMaskFile(tmpFMaskOut)

                thermalGain1040um = (self.b6aMaxRad - self.b6aMinRad) / (self.b6aCalMax - self.b6aCalMin)
                thermalOffset1040um = self.b6aMinRad - self.b6aCalMin * thermalGain1040um
                thermalBand1040um = 0
                thermalInfo = fmask.config.ThermalFileInfo(thermalBand1040um, thermalGain1040um, thermalOffset1040um, 666.09, 1282.71)

                anglesInfo = fmask.config.AnglesFileInfo(inputViewAngleImg, 3, inputViewAngleImg, 2, inputViewAngleImg, 1, inputViewAngleImg, 0)

                fmaskConfig = fmask.config.FmaskConfig(fmask.config.FMASK_LANDSAT47)
                fmaskConfig.setTOARefScaling(float(scaleFactor))
                fmaskConfig.setThermalInfo(thermalInfo)
                fmaskConfig.setAnglesInfo(anglesInfo)
                fmaskConfig.setKeepIntermediates(False)
                fmaskConfig.setVerbose(True)
                fmaskConfig.setTempDir(tmpBaseDIR)
                fmaskConfig.setMinCloudSize(minCloudSize)
                fmaskConfig.setEqn17CloudProbThresh(fmask.config.FmaskConfig.Eqn17CloudProbThresh)
                fmaskConfig.setEqn20NirSnowThresh(fmask.config.FmaskConfig.Eqn20NirSnowThresh)
                fmaskConfig.setEqn20GreenSnowThresh(fmask.config.FmaskConfig.Eqn20GreenSnowThresh)

                # Work out a suitable buffer size, in pixels, dependent on the resolution of the input TOA image
                toaImgInfo = rios.fileinfo.ImageInfo(inputReflImage)
                fmaskConfig.setCloudBufferSize(int(cloudBufferDistance / toaImgInfo.xRes))
                fmaskConfig.setShadowBufferSize(int(shadowBufferDistance / toaImgInfo.xRes))

                fmask.fmask.doFmask(fmaskFilenames, fmaskConfig)

                rsgislib.imagecalc.imageMath(tmpFMaskOut, outputImage, '(b1==2)?1:(b1==3)?2:0', outFormat, rsgislib.TYPE_8UINT)
            elif (cloud_msk_methods == 'LSMSK'):
                if (self.bandQAFile == "") or (not os.path.exists(self.bandQAFile)):
                    raise ARCSIException("The QA band is not present - cannot use this for cloud masking.")

                bqa_img_file = self.bandQAFile
                if not rsgisUtils.doGDALLayersHaveSameProj(bqa_img_file, inputReflImage):
                    bqa_img_file = os.path.join(tmpBaseDIR, tmpBaseName + '_BQA.kea')
                    rsgislib.imageutils.resampleImage2Match(inputReflImage, self.bandQAFile, bqa_img_file, 'KEA',
                                                            'nearestneighbour', rsgislib.TYPE_16UINT, noDataVal=0,
                                                            multicore=False)

                exp = '(b1==752)||(b1==756)||(b1==760)||(b1==764)?1:' \
                      '(b1==928)||(b1==932)||(b1==936)||(b1==940)||(b1==960)||(b1==964)||(b1==968)||(b1==972)?2:0'
                rsgislib.imagecalc.imageMath(bqa_img_file, outputImage, exp, outFormat, rsgislib.TYPE_8UINT)

            else:
                raise ARCSIException(
                    "Landsat only has FMASK and LSMSK cloud masking options; option provided is unknown.")

            if outFormat == 'KEA':
                rsgislib.rastergis.populateStats(outputImage, True, True)
                ratDataset = gdal.Open(outputImage, gdal.GA_Update)
                red = rat.readColumn(ratDataset, 'Red')
                green = rat.readColumn(ratDataset, 'Green')
                blue = rat.readColumn(ratDataset, 'Blue')
                ClassName = numpy.empty_like(red, dtype=numpy.dtype('a255'))

                red[0] = 0
                green[0] = 0
                blue[0] = 0

                if (red.shape[0] == 2) or (red.shape[0] == 3):
                    red[1] = 0
                    green[1] = 0
                    blue[1] = 255
                    ClassName[1] = 'Clouds'

                    if(red.shape[0] == 3):
                        red[2] = 0
                        green[2] = 255
                        blue[2] = 255
                        ClassName[2] = 'Shadows'

                rat.writeColumn(ratDataset, "Red", red)
                rat.writeColumn(ratDataset, "Green", green)
                rat.writeColumn(ratDataset, "Blue", blue)
                rat.writeColumn(ratDataset, "ClassName", ClassName)
                ratDataset = None
            rsgislib.imageutils.copyProjFromImage(outputImage, inputReflImage)

            if not self.debugMode:
                if not tmpDIRExisted:
                    shutil.rmtree(tmpBaseDIR, ignore_errors=True)

            return outputImage
        except Exception as e:
            raise e

    def createCloudMaskDataArray(self, inImgDataArr):
        return inImgDataArr

    def defineDarkShadowImageBand(self):
        return 4

    def calc6SCoefficients(self, aeroProfile, atmosProfile, grdRefl, surfaceAltitude, aotVal, useBRDF):
        sixsCoeffs = numpy.zeros((6, 6), dtype=numpy.float32)
        # Set up 6S model
        s = Py6S.SixS()
        s.atmos_profile = atmosProfile
        s.aero_profile = aeroProfile
        s.ground_reflectance = grdRefl
        s.geometry = Py6S.Geometry.Landsat_TM()
        s.geometry.month = self.acquisitionTime.month
        s.geometry.day = self.acquisitionTime.day
        s.geometry.gmt_decimal_hour = float(self.acquisitionTime.hour) + float(self.acquisitionTime.minute)/60.0
        s.geometry.latitude = self.latCentre
        s.geometry.longitude = self.lonCentre
        s.altitudes = Py6S.Altitudes()
        s.altitudes.set_target_custom_altitude(surfaceAltitude)
        s.altitudes.set_sensor_satellite_level()
        if useBRDF:
            s.atmos_corr = Py6S.AtmosCorr.AtmosCorrBRDFFromRadiance(200)
        else:
            s.atmos_corr = Py6S.AtmosCorr.AtmosCorrLambertianFromRadiance(200)
        s.aot550 = aotVal

        # Band 1
        s.wavelength = Py6S.Wavelength(Py6S.Params.PredefinedWavelengths.LANDSAT_ETM_B1)
        s.run()
        sixsCoeffs[0,0] = float(s.outputs.values['coef_xa'])
        sixsCoeffs[0,1] = float(s.outputs.values['coef_xb'])
        sixsCoeffs[0,2] = float(s.outputs.values['coef_xc'])
        sixsCoeffs[0,3] = float(s.outputs.values['direct_solar_irradiance'])
        sixsCoeffs[0,4] = float(s.outputs.values['diffuse_solar_irradiance'])
        sixsCoeffs[0,5] = float(s.outputs.values['environmental_irradiance'])

        # Band 2
        s.wavelength = Py6S.Wavelength(Py6S.Params.PredefinedWavelengths.LANDSAT_ETM_B2)
        s.run()
        sixsCoeffs[1,0] = float(s.outputs.values['coef_xa'])
        sixsCoeffs[1,1] = float(s.outputs.values['coef_xb'])
        sixsCoeffs[1,2] = float(s.outputs.values['coef_xc'])
        sixsCoeffs[1,3] = float(s.outputs.values['direct_solar_irradiance'])
        sixsCoeffs[1,4] = float(s.outputs.values['diffuse_solar_irradiance'])
        sixsCoeffs[1,5] = float(s.outputs.values['environmental_irradiance'])

        # Band 3
        s.wavelength = Py6S.Wavelength(Py6S.Params.PredefinedWavelengths.LANDSAT_ETM_B3)
        s.run()
        sixsCoeffs[2,0] = float(s.outputs.values['coef_xa'])
        sixsCoeffs[2,1] = float(s.outputs.values['coef_xb'])
        sixsCoeffs[2,2] = float(s.outputs.values['coef_xc'])
        sixsCoeffs[2,3] = float(s.outputs.values['direct_solar_irradiance'])
        sixsCoeffs[2,4] = float(s.outputs.values['diffuse_solar_irradiance'])
        sixsCoeffs[2,5] = float(s.outputs.values['environmental_irradiance'])

        # Band 4
        s.wavelength = Py6S.Wavelength(Py6S.Params.PredefinedWavelengths.LANDSAT_ETM_B4)
        s.run()
        sixsCoeffs[3,0] = float(s.outputs.values['coef_xa'])
        sixsCoeffs[3,1] = float(s.outputs.values['coef_xb'])
        sixsCoeffs[3,2] = float(s.outputs.values['coef_xc'])
        sixsCoeffs[3,3] = float(s.outputs.values['direct_solar_irradiance'])
        sixsCoeffs[3,4] = float(s.outputs.values['diffuse_solar_irradiance'])
        sixsCoeffs[3,5] = float(s.outputs.values['environmental_irradiance'])

        # Band 5
        s.wavelength = Py6S.Wavelength(Py6S.Params.PredefinedWavelengths.LANDSAT_ETM_B5)
        s.run()
        sixsCoeffs[4,0] = float(s.outputs.values['coef_xa'])
        sixsCoeffs[4,1] = float(s.outputs.values['coef_xb'])
        sixsCoeffs[4,2] = float(s.outputs.values['coef_xc'])
        sixsCoeffs[4,3] = float(s.outputs.values['direct_solar_irradiance'])
        sixsCoeffs[4,4] = float(s.outputs.values['diffuse_solar_irradiance'])
        sixsCoeffs[4,5] = float(s.outputs.values['environmental_irradiance'])

        # Band 7
        s.wavelength = Py6S.Wavelength(Py6S.Params.PredefinedWavelengths.LANDSAT_ETM_B7)
        s.run()
        sixsCoeffs[5,0] = float(s.outputs.values['coef_xa'])
        sixsCoeffs[5,1] = float(s.outputs.values['coef_xb'])
        sixsCoeffs[5,2] = float(s.outputs.values['coef_xc'])
        sixsCoeffs[5,3] = float(s.outputs.values['direct_solar_irradiance'])
        sixsCoeffs[5,4] = float(s.outputs.values['diffuse_solar_irradiance'])
        sixsCoeffs[5,5] = float(s.outputs.values['environmental_irradiance'])

        return sixsCoeffs

    def convertImageToSurfaceReflSglParam(self, inputRadImage, outputPath, outputName, outFormat, aeroProfile, atmosProfile, grdRefl, surfaceAltitude, aotVal, useBRDF, scaleFactor):
        print("Converting to Surface Reflectance")
        outputImage = os.path.join(outputPath, outputName)

        imgBandCoeffs = list()

        sixsCoeffs = self.calc6SCoefficients(aeroProfile, atmosProfile, grdRefl, surfaceAltitude, aotVal, useBRDF)

        imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=1, aX=float(sixsCoeffs[0,0]), bX=float(sixsCoeffs[0,1]), cX=float(sixsCoeffs[0,2]), DirIrr=float(sixsCoeffs[0,3]), DifIrr=float(sixsCoeffs[0,4]), EnvIrr=float(sixsCoeffs[0,5])))
        imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=2, aX=float(sixsCoeffs[1,0]), bX=float(sixsCoeffs[1,1]), cX=float(sixsCoeffs[1,2]), DirIrr=float(sixsCoeffs[1,3]), DifIrr=float(sixsCoeffs[1,4]), EnvIrr=float(sixsCoeffs[1,5])))
        imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=3, aX=float(sixsCoeffs[2,0]), bX=float(sixsCoeffs[2,1]), cX=float(sixsCoeffs[2,2]), DirIrr=float(sixsCoeffs[2,3]), DifIrr=float(sixsCoeffs[2,4]), EnvIrr=float(sixsCoeffs[2,5])))
        imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=4, aX=float(sixsCoeffs[3,0]), bX=float(sixsCoeffs[3,1]), cX=float(sixsCoeffs[3,2]), DirIrr=float(sixsCoeffs[3,3]), DifIrr=float(sixsCoeffs[3,4]), EnvIrr=float(sixsCoeffs[3,5])))
        imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=5, aX=float(sixsCoeffs[4,0]), bX=float(sixsCoeffs[4,1]), cX=float(sixsCoeffs[4,2]), DirIrr=float(sixsCoeffs[4,3]), DifIrr=float(sixsCoeffs[4,4]), EnvIrr=float(sixsCoeffs[4,5])))
        imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=6, aX=float(sixsCoeffs[5,0]), bX=float(sixsCoeffs[5,1]), cX=float(sixsCoeffs[5,2]), DirIrr=float(sixsCoeffs[5,3]), DifIrr=float(sixsCoeffs[5,4]), EnvIrr=float(sixsCoeffs[5,5])))

        rsgislib.imagecalibration.apply6SCoeffSingleParam(inputRadImage, outputImage, outFormat, rsgislib.TYPE_16UINT, scaleFactor, 0, True, imgBandCoeffs)

        return outputImage

    def convertImageToSurfaceReflDEMElevLUT(self, inputRadImage, inputDEMFile, outputPath, outputName, outFormat, aeroProfile, atmosProfile, grdRefl, aotVal, useBRDF, surfaceAltitudeMin, surfaceAltitudeMax, scaleFactor, elevCoeffs=None):
        print("Converting to Surface Reflectance")
        outputImage = os.path.join(outputPath, outputName)

        if elevCoeffs is None:
            print("Build an LUT for elevation values.")
            elev6SCoeffsLUT = self.buildElevation6SCoeffLUT(aeroProfile, atmosProfile, grdRefl, aotVal, useBRDF, surfaceAltitudeMin, surfaceAltitudeMax)
            print("LUT has been built.")

            elevCoeffs = list()
            for elevLUT in elev6SCoeffsLUT:
                imgBandCoeffs = list()
                sixsCoeffs = elevLUT.Coeffs
                elevVal = elevLUT.Elev
                imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=1, aX=float(sixsCoeffs[0,0]), bX=float(sixsCoeffs[0,1]), cX=float(sixsCoeffs[0,2]), DirIrr=float(sixsCoeffs[0,3]), DifIrr=float(sixsCoeffs[0,4]), EnvIrr=float(sixsCoeffs[0,5])))
                imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=2, aX=float(sixsCoeffs[1,0]), bX=float(sixsCoeffs[1,1]), cX=float(sixsCoeffs[1,2]), DirIrr=float(sixsCoeffs[1,3]), DifIrr=float(sixsCoeffs[1,4]), EnvIrr=float(sixsCoeffs[1,5])))
                imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=3, aX=float(sixsCoeffs[2,0]), bX=float(sixsCoeffs[2,1]), cX=float(sixsCoeffs[2,2]), DirIrr=float(sixsCoeffs[2,3]), DifIrr=float(sixsCoeffs[2,4]), EnvIrr=float(sixsCoeffs[2,5])))
                imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=4, aX=float(sixsCoeffs[3,0]), bX=float(sixsCoeffs[3,1]), cX=float(sixsCoeffs[3,2]), DirIrr=float(sixsCoeffs[3,3]), DifIrr=float(sixsCoeffs[3,4]), EnvIrr=float(sixsCoeffs[3,5])))
                imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=5, aX=float(sixsCoeffs[4,0]), bX=float(sixsCoeffs[4,1]), cX=float(sixsCoeffs[4,2]), DirIrr=float(sixsCoeffs[4,3]), DifIrr=float(sixsCoeffs[4,4]), EnvIrr=float(sixsCoeffs[4,5])))
                imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=6, aX=float(sixsCoeffs[5,0]), bX=float(sixsCoeffs[5,1]), cX=float(sixsCoeffs[5,2]), DirIrr=float(sixsCoeffs[5,3]), DifIrr=float(sixsCoeffs[5,4]), EnvIrr=float(sixsCoeffs[5,5])))

                elevCoeffs.append(rsgislib.imagecalibration.ElevLUTFeat(Elev=float(elevVal), Coeffs=imgBandCoeffs))

        rsgislib.imagecalibration.apply6SCoeffElevLUTParam(inputRadImage, inputDEMFile, outputImage, outFormat, rsgislib.TYPE_16UINT, scaleFactor, 0, True, elevCoeffs)
        return outputImage, elevCoeffs

    def convertImageToSurfaceReflAOTDEMElevLUT(self, inputRadImage, inputDEMFile, inputAOTImage, outputPath, outputName, outFormat, aeroProfile, atmosProfile, grdRefl, useBRDF, surfaceAltitudeMin, surfaceAltitudeMax, aotMin, aotMax, scaleFactor, elevAOTCoeffs=None):
        print("Converting to Surface Reflectance")
        outputImage = os.path.join(outputPath, outputName)

        if elevAOTCoeffs is None:
            print("Build an LUT for elevation and AOT values.")
            elevAOT6SCoeffsLUT = self.buildElevationAOT6SCoeffLUT(aeroProfile, atmosProfile, grdRefl, useBRDF, surfaceAltitudeMin, surfaceAltitudeMax, aotMin, aotMax)

            elevAOTCoeffs = list()
            for elevLUT in elevAOT6SCoeffsLUT:
                elevVal = elevLUT.Elev
                aotLUT = elevLUT.Coeffs
                aot6SCoeffsOut = list()
                for aotFeat in aotLUT:
                    sixsCoeffs = aotFeat.Coeffs
                    aotVal = aotFeat.AOT
                    imgBandCoeffs = list()
                    imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=1, aX=float(sixsCoeffs[0,0]), bX=float(sixsCoeffs[0,1]), cX=float(sixsCoeffs[0,2]), DirIrr=float(sixsCoeffs[0,3]), DifIrr=float(sixsCoeffs[0,4]), EnvIrr=float(sixsCoeffs[0,5])))
                    imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=2, aX=float(sixsCoeffs[1,0]), bX=float(sixsCoeffs[1,1]), cX=float(sixsCoeffs[1,2]), DirIrr=float(sixsCoeffs[1,3]), DifIrr=float(sixsCoeffs[1,4]), EnvIrr=float(sixsCoeffs[1,5])))
                    imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=3, aX=float(sixsCoeffs[2,0]), bX=float(sixsCoeffs[2,1]), cX=float(sixsCoeffs[2,2]), DirIrr=float(sixsCoeffs[2,3]), DifIrr=float(sixsCoeffs[2,4]), EnvIrr=float(sixsCoeffs[2,5])))
                    imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=4, aX=float(sixsCoeffs[3,0]), bX=float(sixsCoeffs[3,1]), cX=float(sixsCoeffs[3,2]), DirIrr=float(sixsCoeffs[3,3]), DifIrr=float(sixsCoeffs[3,4]), EnvIrr=float(sixsCoeffs[3,5])))
                    imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=5, aX=float(sixsCoeffs[4,0]), bX=float(sixsCoeffs[4,1]), cX=float(sixsCoeffs[4,2]), DirIrr=float(sixsCoeffs[4,3]), DifIrr=float(sixsCoeffs[4,4]), EnvIrr=float(sixsCoeffs[4,5])))
                    imgBandCoeffs.append(rsgislib.imagecalibration.Band6SCoeff(band=6, aX=float(sixsCoeffs[5,0]), bX=float(sixsCoeffs[5,1]), cX=float(sixsCoeffs[5,2]), DirIrr=float(sixsCoeffs[5,3]), DifIrr=float(sixsCoeffs[5,4]), EnvIrr=float(sixsCoeffs[5,5])))
                    aot6SCoeffsOut.append(rsgislib.imagecalibration.AOTLUTFeat(AOT=float(aotVal), Coeffs=imgBandCoeffs))
                elevAOTCoeffs.append(rsgislib.imagecalibration.ElevLUTFeat(Elev=float(elevVal), Coeffs=aot6SCoeffsOut))

        rsgislib.imagecalibration.apply6SCoeffElevAOTLUTParam(inputRadImage, inputDEMFile, inputAOTImage, outputImage, outFormat, rsgislib.TYPE_16UINT, scaleFactor, 0, True, elevAOTCoeffs)

        return outputImage, elevAOTCoeffs

    def run6SToOptimiseAODValue(self, aotVal, radBlueVal, predBlueVal, aeroProfile, atmosProfile, grdRefl, surfaceAltitude):
        """Used as part of the optimastion for identifying values of AOD"""
        print("Testing AOD Val: ", aotVal,)
        s = Py6S.SixS()

        s.atmos_profile = atmosProfile
        s.aero_profile = aeroProfile
        s.ground_reflectance = grdRefl
        s.geometry = Py6S.Geometry.Landsat_TM()
        s.geometry.month = self.acquisitionTime.month
        s.geometry.day = self.acquisitionTime.day
        s.geometry.gmt_decimal_hour = float(self.acquisitionTime.hour) + float(self.acquisitionTime.minute)/60.0
        s.geometry.latitude = self.latCentre
        s.geometry.longitude = self.lonCentre
        s.altitudes = Py6S.Altitudes()
        s.altitudes.set_target_custom_altitude(surfaceAltitude)
        s.altitudes.set_sensor_satellite_level()
        s.atmos_corr = Py6S.AtmosCorr.AtmosCorrLambertianFromRadiance(200)
        s.aot550 = aotVal

        # Band 1 (Blue!)
        s.wavelength = Py6S.Wavelength(Py6S.Params.PredefinedWavelengths.LANDSAT_ETM_B1)
        s.run()
        aX = float(s.outputs.values['coef_xa'])
        bX = float(s.outputs.values['coef_xb'])
        cX = float(s.outputs.values['coef_xc'])
        tmpVal = (aX*radBlueVal)-bX;
        reflBlueVal = tmpVal/(1.0+cX*tmpVal)

        outDist = math.sqrt(math.pow((reflBlueVal - predBlueVal),2))
        print("\taX: ", aX, " bX: ", bX, " cX: ", cX, "     Dist = ", outDist)
        return outDist

    def findDDVTargets(self, inputTOAImage, outputPath, outputName, outFormat, tmpPath):
        try:
            print("Finding dark targets.")
            arcsiUtils = ARCSIUtils()
            tmpBaseName = os.path.splitext(outputName)[0]
            thresImage = os.path.join(tmpPath, tmpBaseName+"_thresd"+arcsiUtils.getFileExtension(outFormat))
            thresImageClumps = os.path.join(tmpPath, tmpBaseName+"_thresdclumps"+arcsiUtils.getFileExtension(outFormat))
            thresImageClumpsRMSmall = os.path.join(tmpPath, tmpBaseName+"_thresdclumpsgt10"+arcsiUtils.getFileExtension(outFormat))
            thresImageClumpsFinal = os.path.join(tmpPath, tmpBaseName+"_thresdclumpsFinal"+arcsiUtils.getFileExtension(outFormat))

            percentiles = rsgislib.imagecalc.bandPercentile(inputTOAImage, 0.05, 0)
            if percentiles[5] > 30:
                b6Thres = str(percentiles[5])
            else:
                b6Thres = "30.0"
            print("SWIR DDV Threshold = ", b6Thres)

            thresMathBands = list()
            thresMathBands.append(rsgislib.imagecalc.BandDefn(bandName='b3', fileName=inputTOAImage, bandIndex=3))
            thresMathBands.append(rsgislib.imagecalc.BandDefn(bandName='b4', fileName=inputTOAImage, bandIndex=4))
            thresMathBands.append(rsgislib.imagecalc.BandDefn(bandName='b6', fileName=inputTOAImage, bandIndex=6))
            rsgislib.imagecalc.bandMath(thresImage, "(b6< " + b6Thres + ")&&(b6!=0)&&(((b4-b3)/(b4+b3))>0.1)?1:0", outFormat, rsgislib.TYPE_8UINT, thresMathBands)
            rsgislib.segmentation.clump(thresImage, thresImageClumps, outFormat, False, 0.0)
            rsgislib.rastergis.populateStats(thresImageClumps, True, True)
            rsgislib.segmentation.rmSmallClumps(thresImageClumps, thresImageClumpsRMSmall, 100, outFormat)
            rsgislib.segmentation.relabelClumps(thresImageClumpsRMSmall, thresImageClumpsFinal, outFormat, False)
            rsgislib.rastergis.populateStats(thresImageClumpsFinal, True, True)

            if not self.debugMode:
                gdalDriver = gdal.GetDriverByName(outFormat)
                gdalDriver.Delete(thresImage)
                gdalDriver.Delete(thresImageClumps)
                gdalDriver.Delete(thresImageClumpsRMSmall)

            return thresImageClumpsFinal
        except Exception as e:
            raise e

    def estimateImageToAODUsingDDV(self, inputRADImage, inputTOAImage, inputDEMFile, shadowMask, outputPath, outputName, outFormat, tmpPath, aeroProfile, atmosProfile, grdRefl, aotValMin, aotValMax):
        print("Estimating AOD through Blue - SWIR relationship.")
        try:
            arcsiUtils = ARCSIUtils()

            outputAOTImage = os.path.join(outputPath, outputName)

            thresImageClumpsFinal = self.findDDVTargets(inputTOAImage, outputPath, outputName, "KEA", tmpPath)

            stats2CalcTOA = list()
            stats2CalcTOA.append(rsgislib.rastergis.BandAttStats(band=1, meanField="MeanElev"))
            rsgislib.rastergis.populateRATWithStats(inputDEMFile, thresImageClumpsFinal, stats2CalcTOA)

            stats2CalcTOA = list()
            stats2CalcTOA.append(rsgislib.rastergis.BandAttStats(band=1, minField="MinB1TOA", meanField="MeanB1TOA"))
            stats2CalcTOA.append(rsgislib.rastergis.BandAttStats(band=6, minField="MinB7TOA", meanField="MeanB7TOA"))
            rsgislib.rastergis.populateRATWithStats(inputTOAImage, thresImageClumpsFinal, stats2CalcTOA)
            stats2CalcRad = list()
            stats2CalcRad.append(rsgislib.rastergis.BandAttStats(band=1, minField="MinB1RAD", meanField="MeanB1RAD"))
            rsgislib.rastergis.populateRATWithStats(inputRADImage, thresImageClumpsFinal, stats2CalcRad)

            ratDS = gdal.Open(thresImageClumpsFinal, gdal.GA_Update)
            Histogram = rat.readColumn(ratDS, "Histogram")
            MeanElev = rat.readColumn(ratDS, "MeanElev")

            selected = Histogram * 2
            selected[...] = 1
            selected[0] = 0
            rat.writeColumn(ratDS, "Selected", selected)
            ratDS = None

            rsgislib.rastergis.spatialLocation(thresImageClumpsFinal, "Eastings", "Northings")
            rsgislib.rastergis.selectClumpsOnGrid(thresImageClumpsFinal, "Selected", "PredictAOTFor", "Eastings", "Northings", "MinB7TOA", "min", 10, 10)

            ratDS = gdal.Open(thresImageClumpsFinal, gdal.GA_Update)
            MeanB1TOA = rat.readColumn(ratDS, "MeanB1TOA")
            MeanB7TOA = rat.readColumn(ratDS, "MeanB7TOA")
            MeanB1RAD = rat.readColumn(ratDS, "MeanB1RAD")
            PredictAOTFor = rat.readColumn(ratDS, "PredictAOTFor")

            PredB1Refl = (MeanB7TOA/1000) * 0.33

            rat.writeColumn(ratDS, "PredB1Refl", PredB1Refl)

            numAOTValTests = int(math.ceil((aotValMax - aotValMin)/0.05))+1

            if not numAOTValTests >= 1:
                raise ARCSIException("min and max AOT range are too close together, they need to be at least 0.05 apart.")

            cAOT = aotValMin
            cDist = 0.0
            minAOT = 0.0
            minDist = 0.0

            aotVals = numpy.zeros_like(MeanB1RAD, dtype=numpy.float)

            for i in range(len(MeanB1RAD)):
                if PredictAOTFor[i] == 1:
                    print("Predicting AOD for Segment ", i)
                    for j in range(numAOTValTests):
                        cAOT = aotValMin + (0.05 * j)
                        cDist = self.run6SToOptimiseAODValue(cAOT, MeanB1RAD[i], PredB1Refl[i], aeroProfile, atmosProfile, grdRefl, MeanElev[i]/1000)
                        if j == 0:
                            minAOT = cAOT
                            minDist = cDist
                        elif cDist < minDist:
                            minAOT = cAOT
                            minDist = cDist
                    #predAOTArgs = (MeanB1RAD[i], PredB1Refl[i], aeroProfile, atmosProfile, grdRefl, MeanElev[i])
                    #res = minimize(self.run6SToOptimiseAODValue, minAOT, method='nelder-mead', options={'maxiter': 20, 'xtol': 0.001, 'disp': True}, args=predAOTArgs)
                    #aotVals[i] = res.x[0]
                    aotVals[i] = minAOT
                    print("IDENTIFIED AOT: ", aotVals[i])
                else:
                    aotVals[i] = 0
            rat.writeColumn(ratDS, "AOT", aotVals)

            Eastings = rat.readColumn(ratDS, "Eastings")
            Northings = rat.readColumn(ratDS, "Northings")
            ratDS = None

            Eastings = Eastings[PredictAOTFor!=0]
            Northings = Northings[PredictAOTFor!=0]
            aotVals = aotVals[PredictAOTFor!=0]

            interpSmoothing = 10.0
            self.interpolateImageFromPointData(inputTOAImage, Eastings, Northings, aotVals, outputAOTImage, outFormat, interpSmoothing, True, 0.05)

            if not self.debugMode:
                gdalDriver = gdal.GetDriverByName("KEA")
                gdalDriver.Delete(thresImageClumpsFinal)

            return outputAOTImage
        except Exception as e:
            raise e

    def estimateImageToAODUsingDOS(self, inputRADImage, inputTOAImage, inputDEMFile, shadowMask, outputPath, outputName, outFormat, tmpPath, aeroProfile, atmosProfile, grdRefl, aotValMin, aotValMax, globalDOS, simpleDOS, dosOutRefl):
        try:
            print("Estimating AOD Using DOS")
            arcsiUtils = ARCSIUtils()

            outputAOTImage = os.path.join(outputPath, outputName)
            tmpBaseName = os.path.splitext(outputName)[0]
            imgExtension = arcsiUtils.getFileExtension(outFormat)


            dosBlueImage = ""
            minObjSize = 5
            darkPxlPercentile = 0.01
            blockSize = 1000
            if simpleDOS:
                outputDOSBlueName = tmpBaseName + "DOSBlue" + imgExtension
                dosBlueImage, bandOff = self.convertImageBandToReflectanceSimpleDarkSubtract(inputTOAImage, outputPath, outputDOSBlueName, outFormat, dosOutRefl, 1)
            elif globalDOS:
                dosBlueImage = self.performDOSOnSingleBand(inputTOAImage, 1, outputPath, tmpBaseName, "Blue", "KEA", tmpPath, minObjSize, darkPxlPercentile, dosOutRefl)
            else:
                dosBlueImage = self.performLocalDOSOnSingleBand(inputTOAImage, 1, outputPath, tmpBaseName, "Blue", "KEA", tmpPath, minObjSize, darkPxlPercentile, blockSize, dosOutRefl)


            thresImageClumpsFinal = os.path.join(tmpPath, tmpBaseName + "_clumps" + imgExtension)
            rsgislib.segmentation.segutils.runShepherdSegmentation(inputTOAImage, thresImageClumpsFinal, tmpath=tmpPath, gdalformat="KEA", numClusters=20, minPxls=10, bands=[4,5,3], processInMem=True)

            stats2CalcTOA = list()
            stats2CalcTOA.append(rsgislib.rastergis.BandAttStats(band=1, meanField="MeanElev"))
            rsgislib.rastergis.populateRATWithStats(inputDEMFile, thresImageClumpsFinal, stats2CalcTOA)

            stats2CalcTOA = list()
            stats2CalcTOA.append(rsgislib.rastergis.BandAttStats(band=1, meanField="MeanB1DOS"))
            rsgislib.rastergis.populateRATWithStats(dosBlueImage, thresImageClumpsFinal, stats2CalcTOA)

            stats2CalcRad = list()
            stats2CalcRad.append(rsgislib.rastergis.BandAttStats(band=1, meanField="MeanB1RAD"))
            stats2CalcRad.append(rsgislib.rastergis.BandAttStats(band=4, meanField="MeanB4RAD"))
            stats2CalcRad.append(rsgislib.rastergis.BandAttStats(band=3, meanField="MeanB3RAD"))
            rsgislib.rastergis.populateRATWithStats(inputRADImage, thresImageClumpsFinal, stats2CalcRad)

            ratDS = gdal.Open(thresImageClumpsFinal, gdal.GA_Update)
            Histogram = rat.readColumn(ratDS, "Histogram")
            MeanElev = rat.readColumn(ratDS, "MeanElev")

            MeanB4RAD = rat.readColumn(ratDS, "MeanB4RAD")
            MeanB3RAD = rat.readColumn(ratDS, "MeanB3RAD")

            radNDVI = (MeanB4RAD - MeanB3RAD)/(MeanB4RAD + MeanB3RAD)

            selected = Histogram * 2
            selected[...] = 0
            selected[radNDVI>0.2] = 1
            rat.writeColumn(ratDS, "Selected", selected)
            ratDS = None

            rsgislib.rastergis.spatialLocation(thresImageClumpsFinal, "Eastings", "Northings")
            rsgislib.rastergis.selectClumpsOnGrid(thresImageClumpsFinal, "Selected", "PredictAOTFor", "Eastings", "Northings", "MeanB1DOS", "min", 10, 10)

            ratDS = gdal.Open(thresImageClumpsFinal, gdal.GA_Update)
            MeanB1DOS = rat.readColumn(ratDS, "MeanB1DOS")
            MeanB1DOS = MeanB1DOS / 1000
            MeanB1RAD = rat.readColumn(ratDS, "MeanB1RAD")
            PredictAOTFor = rat.readColumn(ratDS, "PredictAOTFor")

            numAOTValTests = int(math.ceil((aotValMax - aotValMin)/0.05))+1

            if not numAOTValTests >= 1:
                raise ARCSIException("min and max AOT range are too close together, they need to be at least 0.05 apart.")

            cAOT = aotValMin
            cDist = 0.0
            minAOT = 0.0
            minDist = 0.0

            aotVals = numpy.zeros_like(MeanB1RAD, dtype=numpy.float)

            for i in range(len(MeanB1RAD)):
                if PredictAOTFor[i] == 1:
                    print("Predicting AOD for Segment ", i)
                    for j in range(numAOTValTests):
                        cAOT = aotValMin + (0.05 * j)
                        cDist = self.run6SToOptimiseAODValue(cAOT, MeanB1RAD[i], MeanB1DOS[i], aeroProfile, atmosProfile, grdRefl, MeanElev[i]/1000)
                        if j == 0:
                            minAOT = cAOT
                            minDist = cDist
                        elif cDist < minDist:
                            minAOT = cAOT
                            minDist = cDist
                    #predAOTArgs = (MeanB1RAD[i], MeanB1DOS[i], aeroProfile, atmosProfile, grdRefl, MeanElev[i])
                    #res = minimize(self.run6SToOptimiseAODValue, minAOT, method='nelder-mead', options={'maxiter': 20, 'xtol': 0.001, 'disp': True}, args=predAOTArgs)
                    #aotVals[i] = res.x[0]
                    aotVals[i] = minAOT
                    print("IDENTIFIED AOT: ", aotVals[i])
                else:
                    aotVals[i] = 0
            rat.writeColumn(ratDS, "AOT", aotVals)

            Eastings = rat.readColumn(ratDS, "Eastings")
            Northings = rat.readColumn(ratDS, "Northings")
            ratDS = None

            Eastings = Eastings[PredictAOTFor!=0]
            Northings = Northings[PredictAOTFor!=0]
            aotVals = aotVals[PredictAOTFor!=0]

            interpSmoothing = 10.0
            self.interpolateImageFromPointData(inputTOAImage, Eastings, Northings, aotVals, outputAOTImage, outFormat, interpSmoothing, True, 0.05)

            if not self.debugMode:
                gdalDriver = gdal.GetDriverByName("KEA")
                gdalDriver.Delete(thresImageClumpsFinal)
                gdalDriver.Delete(dosBlueImage)

            return outputAOTImage
        except Exception as e:
            raise e

    def estimateSingleAOTFromDOS(self, radianceImage, toaImage, inputDEMFile, tmpPath, outputName, outFormat, aeroProfile, atmosProfile, grdRefl, minAOT, maxAOT, dosOutRefl):
        try:
            return self.estimateSingleAOTFromDOSBandImpl(radianceImage, toaImage, inputDEMFile, tmpPath, outputName, outFormat, aeroProfile, atmosProfile, grdRefl, minAOT, maxAOT, dosOutRefl, 1)
        except Exception as e:
            raise

    def setBandNames(self, imageFile):
        dataset = gdal.Open(imageFile, gdal.GA_Update)
        dataset.GetRasterBand(1).SetDescription("Blue")
        dataset.GetRasterBand(2).SetDescription("Green")
        dataset.GetRasterBand(3).SetDescription("Red")
        dataset.GetRasterBand(4).SetDescription("NIR")
        dataset.GetRasterBand(5).SetDescription("SWIR1")
        dataset.GetRasterBand(6).SetDescription("SWIR2")
        dataset = None

    def cleanLocalFollowProcessing(self):
        print("")



