from build123d import *
from ocp_vscode import *
import cadquery as cq
import time
import math
import sys
from dataclasses import dataclass, field
import bd_warehouse.thread, bd_warehouse.fastener 
from pathlib import Path

# Cube generator tool
def generateCube(x, y, z):

    # nested arm generator for generating the arms
    with BuildPart() as rectangle:
        with BuildSketch(Plane.XZ) as sketch:
            sketch = Rectangle(x,z)
        extrude(amount = y)
    return rectangle.part

# Rotation tool for moving parts. This automates a lot of annoying stuff
def moveMe(item, displacementVector=None, rotationVector=None, rotationAxis=None, rotationAngle=None):
    if rotationAxis is not None and rotationVector is not None:
        item = item.rotate(
        axis = Axis(rotationAxis, rotationVector),
        angle = rotationAngle
        ).translate(displacementVector)
    if displacementVector is not None:
        item = item.translate(displacementVector)
    else:
        item = item
    return item

    # At this point in the code I wanted tools


# all this will be need to reworked for use with rotational planes and the like. for now it works fine 
def obtainFaces(input):
    xNormalFaces = input.faces().filter_by(Axis.X).filter_by(GeomType.PLANE).sort_by(Axis.X)
    zNormalFaces = input.faces().filter_by(Axis.Z).filter_by(GeomType.PLANE).sort_by(Axis.Z)
    return(xNormalFaces, zNormalFaces)

def filletMe(input,faceindex1,faceindex2, rad):
    xNormalFaces, zNormalFaces = obtainFaces(input)
    sharedEdges = xNormalFaces[faceindex1].edges() & zNormalFaces[faceindex2].edges()
    inputChamfered = fillet(sharedEdges, radius = rad)
    return(inputChamfered)

def flattenToXY(face):
    z = face.center().Z
    return face.translate((0,0,-z))

# Lofting the region between nubs 2 and 4
def findY(f):
    return f.normal_at().Y

def findX(f):
    return f.normal_at().X

def findZ(f):
    return f.normal_at().Z

# x is the y-ward body, y is the -y ward body.
def loftMe(x,y,z=None):
    if z is None or z == 1:
        loftRotationVector = (0,0,1)
        loftRotationAngle = 180
        target_face1 = min(x.faces(), key=findY)
        target_face2 = max(y.faces(), key=findY)
        part = loft([target_face1,target_face2])
        part_rotated = part.rotate(
                axis = Axis(part.center(), loftRotationVector),
                angle = loftRotationAngle
            )
    if z == 0: 
        loftRotationVector = (0,0,1)
        loftRotationAngle = 180
        target_face1 = min(x.faces(), key=findX)
        target_face2 = max(y.faces(), key=findX)
        part = loft([target_face1,target_face2])
        part_rotated = part.rotate(
                axis = Axis(part.center(), loftRotationVector),
                angle = loftRotationAngle
            )
    elif z == 2: 
        loftRotationVector = (0,1,0) # Rotates about y axis
        loftRotationAngle = 180
        target_face1 = min(x.faces(), key=findZ)
        target_face2 = max(y.faces(), key=findZ)
        part = loft([target_face1,target_face2])
        part_rotated = part.rotate(
                axis = Axis(part.center(), loftRotationVector),
                angle = loftRotationAngle
            )

    
    return part_rotated

# need to make this rotatable with our metaphorical theta quantity for arbor rotation
# Function for building positional arms
def armConstructor(i,x,z): # i = nub index, x = nub, z = shaft upper boundary plane


    # Universal internal properties
    cylinderAttachmentPointZDisplacement = 2.5
    cylinderAttachmentPointYThickness = 3.0
    armXThickness = 2.5

    # Outside arms 
    if i == 0 or i == 3:
        cylinderAttachmentPointXDisplacement = 13
        cylinderAttachmentPointArmLength = 4

    # Middle arms
    if i == 1 or i == 2:
        cylinderAttachmentPointXDisplacement = 14
        cylinderAttachmentPointArmLength = 2

    # Vectors
    armDuplicatorVector = (0,0,1)
    armDuplicatorAngle = 180

    outerRectangleWidth = cylinderAttachmentPointArmLength + armXThickness
    outerRectangleHeight = 0 - z.origin.Z - cylinderAttachmentPointZDisplacement + 2.5

    innerRectangleWidth = outerRectangleWidth - armXThickness
    innerRectangleHeight = outerRectangleHeight - cylinderAttachmentPointZDisplacement

    homingCubeHeight = 2.5
    homingCubeWidth = 0.1
    homingCubeDepth = 3.0

    outerRectangleTranslationVector = (-cylinderAttachmentPointXDisplacement + outerRectangleWidth/2, z.origin.Y + cylinderAttachmentPointYThickness/2, -cylinderAttachmentPointZDisplacement - outerRectangleHeight/2)
    innerRectangleTranslationVector = (-cylinderAttachmentPointXDisplacement + innerRectangleWidth/2, z.origin.Y + cylinderAttachmentPointYThickness/2,  -cylinderAttachmentPointZDisplacement - innerRectangleHeight/2 - (outerRectangleHeight - innerRectangleHeight))
    homingCubeTranslationVector = (-cylinderAttachmentPointXDisplacement + homingCubeWidth/2 + outerRectangleWidth, z.origin.Y + homingCubeDepth/2,  -cylinderAttachmentPointZDisplacement - homingCubeHeight/2 - (outerRectangleHeight - homingCubeHeight))

    # nested arm generator for generating the arms
    outerCube = moveMe(generateCube(outerRectangleWidth,cylinderAttachmentPointYThickness,outerRectangleHeight),outerRectangleTranslationVector)
    innerCube = moveMe(generateCube(innerRectangleWidth,cylinderAttachmentPointYThickness,innerRectangleHeight),innerRectangleTranslationVector)
    homingCube = moveMe(generateCube(homingCubeWidth,homingCubeDepth,homingCubeHeight),homingCubeTranslationVector)

    # Lofts
    loft1 = loftMe(x, homingCube, 0)

    """
    with BuildPart() as rectangle:
        with BuildSketch(Plane.XZ) as sketch:
            sketch = Rectangle(outerRectangleWidth,outerRectangleHeight)
        extrude(amount = cylinderAttachmentPointYThickness)
        outerRectangle = rectangle.part.translate(outerRectangleTranslationVector)
        """
    """
    with BuildPart() as rectangle:
        with BuildSketch(Plane.XZ) as sketch:
            sketch = Rectangle(innerRectangleWidth,innerRectangleHeight)
        extrude(amount = cylinderAttachmentPointYThickness)
        innerRectangle = rectangle.part.translate(innerRectangleTranslationVector)
    """
    

    
    homingRectangle = []

    # Constructing final part
    with BuildPart() as arm1:
        add(outerCube)
        add(homingCube)
        add(innerCube, mode=Mode.SUBTRACT)
        add(loft1)

    # fillet-ing final part for those bits which may be filleted internally
    input = arm1
    armTest = arm1


    
    xEdges = [1,2,2,1]
    zEdges = [0,1,3,2]
    rads = [4,2,2,1]
    for b, x in enumerate(xEdges):
        input = filletMe(input,x,zEdges[b],rads[b])
    """
    # The below is sloppy and will eventually be a function on a day when I feel like cleaning up this code
    # Note: this is now a function 8/12/26
    xNormalFaces, zNormalFaces = obtainFaces(input)
    sharedEdges1 = xNormalFaces[1].edges() & zNormalFaces[0].edges()
    inputChamfered1 = fillet(sharedEdges1, radius = 4)

    xNormalFaces, zNormalFaces = obtainFaces(inputChamfered1)
    sharedEdges2 = xNormalFaces[2].edges() & zNormalFaces[1].edges()
    inputChamfered2 = fillet(sharedEdges2, radius = 2)

    xNormalFaces, zNormalFaces = obtainFaces(inputChamfered2)
    sharedEdges3 = xNormalFaces[2].edges() & zNormalFaces[3].edges()
    inputChamfered3 = fillet(sharedEdges3, radius = 2)

    xNormalFaces, zNormalFaces = obtainFaces(inputChamfered3)
    sharedEdges4 = xNormalFaces[1].edges() & zNormalFaces[2].edges()
    inputChamfered4 = fillet(sharedEdges4, radius = 1)
    """
    arm1 = input
    
    # arm rotator and duplicator (mirror engine) (Problem: Currently works only for symmetric special solutions. Need to decouple the rotator from the pre-existing translation.)
    arm2 = arm1.rotate(
        axis = Axis(z.origin, armDuplicatorVector),
                    angle = armDuplicatorAngle
    )
    return (arm1,arm2,armTest)

def chamberCylinder(chamberIdentity, diagnosticMode,smallDiagnosticTime=0.1,largeDiagnosticTime=0.5):

    # Timer for keeping track of how long the basis cyinder takes to make
    startTime = time.perf_counter()


    # This is a function which builds our basisCylinder. 
    # To start with, we need a chamberIdentity to know the parameters of the basisCylinder we are going to build.
    if chamberIdentity == "GoliathPosterior":
        # Parameters for cylindrical shapes for the basis cylidner
        chamberRadius1=27.5/2 
        chamberRadius2=30.150/2 - 0.025  - 0.05 #0.025mm thicken step in arbor npx backbone. built in here to the radius
        chamberRadius3=36/2
        chamberGripOuterHeight=10
        chamberGripInnerHeight=5

        # Cutaway triangle parameters
        cutTrianglePrimaryAngle=123.547500 # This is the cutout angle in the basis cylinder
        cutTriangleSecondaryAngle=88.546500 # This is the cutout angle relative to the topmost throughhole axis
        cutTriangleHeight=4
        triangleAngle = 123
        triangleThickness = 4
        vertices1 = (0,0,0)
        vertices2 = (-2*chamberRadius3,0,0)
        vertices3 = (-3*chamberRadius3*(math.cos(math.radians(triangleAngle))), -3*chamberRadius3*(math.sin(math.radians(triangleAngle))),0)

        # Throughhole parameters
        throughHoleAngle=90.0 # This is the angle between the throughholes
        throughHoleRadius=3.2600/2 # This is toleranced for a 4-40 screw. Note: This needs to be used for Goliath Posterior
        ThroughHoleRadius2_56=2.500/2 # This is toleranced for a 2-56 screw. Note: This is for both of Malachi's chambers, and for Goliath Anterior.
        clearanceRadius = 2.5 # This is to allow for socket caps to clear the 45 degree bits on the sides of the basis cylinder.

        # Directional indicator triangle parameters
        indicatorTriangleAngle = -1 * (33.456000 + throughHoleAngle)
        indicatorTriangleSideLength = 3.46410
        indicatorTriangleInternalAngles = 180/3
        indicatorOffset = 3.0 / 2
        indicatorHorizontalDisplacement = 14.50000
        indicatorTotalYDisplacement = indicatorHorizontalDisplacement + indicatorOffset + (chamberRadius3 - chamberRadius1)/2
        indicatorTriangleThickness = 0.50000
    
    # elemental shapes of basis cylinder constructed below. 

    # Cylinder parts

    # This is a movement vector which moves the cylinders where I want them
    cylinderTranslationVector=(0,0,(chamberGripOuterHeight-chamberGripInnerHeight)/2)


    # Constructing initial primitive cylinders
    cylinder1 = Cylinder(radius=chamberRadius1, height=chamberGripOuterHeight)
    cylinder2 = Cylinder(radius=chamberRadius2, height=chamberGripInnerHeight).translate(cylinderTranslationVector)
    cylinder3 = Cylinder(radius=chamberRadius3, height=chamberGripOuterHeight)

    # Chamber screw throughholes: Primitive cylinders and translation and rotation vectors to move them
    throughHole1TranslationVector=(0,(chamberRadius2+chamberRadius3)/2,1.15100+throughHoleRadius)
    throughHole1RotationVector=(1,0,0)

    throughHole2TranslationVector=((chamberRadius2+chamberRadius3)/2,0,1.15100+throughHoleRadius)
    throughHole2RotationVector=(0,1,0)

    throughHole1Cylinder = Cylinder(radius=throughHoleRadius, height=chamberRadius1/2).rotate(
        axis = Axis(Vector(0,0,0), throughHole1RotationVector),
        angle=90
    ).translate(throughHole1TranslationVector)

    throughHole2Cylinder = Cylinder(radius=throughHoleRadius,height=chamberRadius1/2).rotate(
        axis = Axis(Vector(0,0,0), throughHole2RotationVector),
        angle = 90
    ).translate(throughHole2TranslationVector)

    # This creates clearance cylinders which are rotated to the same positions as the throughholes, allowing for use later on to create socket cap clearance. 
    clearanceCylinder1 = Cylinder(radius=clearanceRadius, height=chamberRadius1).rotate(
        axis = Axis(Vector(0,0,0), throughHole1RotationVector),
        angle=90
    ).translate(throughHole1TranslationVector)

    clearanceCylinder2 = Cylinder(radius=clearanceRadius, height=chamberRadius1).rotate(
        axis = Axis(Vector(0,0,0), throughHole2RotationVector),
        angle=90
    ).translate(throughHole2TranslationVector)

    # Cutaway Triangle primitives, movement
    with BuildPart() as bp:
        with BuildSketch():
            Polygon(vertices1, vertices2, vertices3, align=None)
        extrude(amount=triangleThickness)

    basisTriangle = bp.part.translate((0,0,(chamberGripOuterHeight/2 - triangleThickness)))

    # Directional Indicator Triangle primitives
    with BuildPart() as bp:
        with BuildSketch():
            Polygon((-indicatorOffset,0,0), (indicatorOffset,0,0), (0,indicatorOffset*2,0), align=None)
        extrude(amount=indicatorTriangleThickness)

    indicatorTriangleTranslationVector = (0,indicatorHorizontalDisplacement,-(indicatorTriangleThickness + chamberGripOuterHeight)/2)
    indicatorTriangleRotationVector = (0,0,1)

    indicatorTriangle = bp.part.translate(indicatorTriangleTranslationVector).rotate(
        axis = Axis(Vector(0,0,0), indicatorTriangleRotationVector),
        angle = indicatorTriangleAngle
    )

    # We need 45 degree screw holes, so this is where we're going to build those for later addition to the basis cylinder
    # Note: In Anna's original CAD the screw hole does not infiltrate the GT frame proper, but rather stays inside the 45 degree block.
    # First we have to use the +Z axis and its corresponding indicator triangle as a reference to offset the location. Essentially we're just building a rotation vector. 
    # Generating threaded screw inserts / holes

    threadDepth = 3.5
    threadDiameter = 3.0
    threadPitch = 0.5
    interferenceConstant = 0.15

    ridge = bd_warehouse.thread.IsoThread(
        major_diameter = threadDiameter,
        pitch = threadPitch,
        length = threadDepth,
        external = False,
        interference = interferenceConstant,
        align = (Align.CENTER, Align.CENTER, Align.MIN)
    )

    outerCylinder = Cylinder(radius = threadDiameter/2, height = threadDepth, align = (Align.CENTER, Align.CENTER, Align.MIN))

    threadedInsert = outerCylinder - ridge

    threadedInsertMoveVector = (0,0,-1)

    threadedInsertMoved = threadedInsert.translate(threadedInsertMoveVector)

    threadedInsertRotationVector = (1,0,0)
    threadedInsertTranslationVector = (0, -3, 0)

    threadedInsertRotated = threadedInsertMoved.rotate(
        axis = Axis(Vector(0,0,0), threadedInsertRotationVector),
        angle = -45
    ).translate(threadedInsertTranslationVector)

    # Generating 45 degree screwholes

    # constant d = 3 + 17.74824
    displacementNumber = 22.74824 - 18 # This float comes from Onshape. Center of chamber to edge of cube. It's subtracted from the initial chamberradius3 value in a variable agnostic fashion.
    # essentially the above is a constant offset which can be used with any chamber radius size to appropriately locate the edge cubes.
    cubeYDisplacement = displacementNumber + chamberRadius3
    cubeZDisplacement = -3
    cubeXDisplacement = 0
    centralRotatorAngle = -15
    iteratorRotatorAngle = 120
    translatedRotatedCubes = []


    newCube = generateCube(6,6,6)

    cubeEdgesForChamfer = newCube.edges().filter_by(GeomType.LINE).filter_by(lambda e: e.center().Z > -.1).filter_by(lambda e: e.center().Y > -.1).filter_by(lambda e: abs(e.position_at(0).Z - e.position_at(1).Z) < 1e-6)

    newChamferedCube = chamfer(cubeEdgesForChamfer, length = 3)


    # Translation and rotation vectors
    cubeTranslationVector = (cubeXDisplacement, cubeYDisplacement, cubeZDisplacement)
    cubeRotationVector = (0,0,1)

    newChamferedCubeWithScrewHole = newChamferedCube - threadedInsertRotated

    translatedCube = newChamferedCubeWithScrewHole.translate(cubeTranslationVector)

    translatedRotatedCube = translatedCube.rotate(
        axis = Axis(Vector(0,0,0), cubeRotationVector),
        angle = centralRotatorAngle)
    translatedRotatedCubes.append(translatedRotatedCube)

    translatedRotatedCube2 = translatedCube.rotate(
        axis = Axis(Vector(0,0,0), cubeRotationVector),
        angle = centralRotatorAngle + iteratorRotatorAngle)
    translatedRotatedCubes.append(translatedRotatedCube2)

    translatedRotatedCube3 = translatedCube.rotate(
        axis = Axis(Vector(0,0,0), cubeRotationVector),
        angle = centralRotatorAngle + iteratorRotatorAngle*2)
    translatedRotatedCubes.append(translatedRotatedCube3)

    # Building the whole basis cylinder

    # Doing the initial construction of the basis cylinder
    with BuildPart() as preBasisCylinder:
        add(cylinder3) # adding outermost cylinder
        add(cylinder1, mode=Mode.SUBTRACT) # Carving at outermost cylinder
        add(cylinder2, mode=Mode.SUBTRACT) # Carving again
        add(throughHole1Cylinder, mode=Mode.SUBTRACT) # Cutting throughholes
        add(throughHole2Cylinder, mode=Mode.SUBTRACT)
        add(basisTriangle, mode=Mode.SUBTRACT) # Adding the cutaway to accomodate skull structure
        add(indicatorTriangle) # adding indicator triangle for orienteering purposes

    # Flipping the cylinder, since I decided building it upside-down at an odd angle was a great idea
    basisCylinderRotationVector1 = (1,0,0)
    preBasisCylinder = preBasisCylinder.part.rotate(
        axis = Axis(Vector(0,0,0), basisCylinderRotationVector1),
        angle = 180
    )

    # Rotating the cylinder so the indicator triangle points to +y
    basisCylinderRotationVector2 = (0,0,1)
    preBasisCylinder = preBasisCylinder.rotate(
        axis = Axis(Vector(0,0,0), basisCylinderRotationVector2),
        angle = 180 - (33.456000 + throughHoleAngle) 
    )

    # Translating the cylinder down 5mm in y axis so it aligns correctly with the chamber mesh. See note in next code box.
    basisCylinderTranslationVector = (0,0,-5)
    preBasisCylinderRotated = preBasisCylinder.translate(basisCylinderTranslationVector)

    # Flipping clearance cylinders with the same vectors as the basis cylinder, so they can be used to create socket cap clearance holes in the basis cylinder.


    # Putting them into a list to iterate through, then rotating and translating them to the same position as the basis cylinder.
    clearanceCylinders = []
    clearanceCylinders.append(clearanceCylinder1)
    clearanceCylinders.append(clearanceCylinder2)
    clearanceCylindersRotated = []

    for i, x in enumerate(clearanceCylinders):
        clearanceCylindersRotated.append(x.rotate(
            axis = Axis(Vector(0,0,0), basisCylinderRotationVector1),
            angle = 180
        ).rotate(
            axis = Axis(Vector(0,0,0), basisCylinderRotationVector2),
            angle = 180 - (33.456000 + throughHoleAngle) 
        ).translate(basisCylinderTranslationVector))

    # Now we check for the overlap of the 45 degree screw hole cubes with the clearance cylinders. If there's overlap we combine in buildpart and subtract clearance cylinders. no overlap = continue
    # This does not actually control combination; this just functions for diagnostic purposes. 
    if diagnosticMode == 1:
        for i, x in enumerate(translatedRotatedCubes):
            for j, y in enumerate(clearanceCylinders):
                overlap = x & y
                if overlap is not None and overlap.volume > 1e-9:
                    print(f"Cube {i} intersects with Clearance Cylinder {j}.")
                else:
                    print(f"Cube {i} does not intersect with Clearance Cylinder {j}.")

    # Subtract clearance cylinders from the 45 degree screw hole cubes and combine them into a single part for addition to the basis cylinder.
    with BuildPart() as finalScrewHoles:
        add(translatedRotatedCubes)
        add(clearanceCylindersRotated, mode=Mode.SUBTRACT)

    i = 0
    # Pre-fusion chamfers. Use geometry to isolate faces and identify edges as join points between two faces. Merge internal edges this way
    input = preBasisCylinderRotated
    # all this will be need to reworked for use with rotational planes and the like. for now it works fine 
    xNormalFaces, zNormalFaces = obtainFaces(input)
    faceList = input.faces()

    targetVFace = [faceList[9], faceList[11]]
    targetZFace = [zNormalFaces[0], zNormalFaces[1]]


    vIndicies = [9,6,6,8]
    zIndicies = [0,0,0,0]
    rads = [1,1,6,6]
    # Compacted code 
    for i, x in enumerate(zIndicies):
        if i == 2 or i == 3:
            xNormalFaces, zNormalFaces = obtainFaces(input)
            faceList=input.faces()
            targetZFace = [zNormalFaces[0], zNormalFaces[1]]
            sharedEdges = faceList[vIndicies[i]].edges() & targetZFace[zIndicies[i]].edges()
            input = fillet(sharedEdges, radius = rads[i])
            if diagnosticMode == 1:
                show(faceList[vIndicies[i]],targetZFace[zIndicies[i]],input)
                time.sleep(smallDiagnosticTime)
        else:
            xNormalFaces, zNormalFaces = obtainFaces(input)
            faceList = input.faces()
            targetZFace = [zNormalFaces[0], zNormalFaces[1]]
            sharedEdges = faceList[vIndicies[i]].edges() & targetZFace[zIndicies[i]].edges()
            input = chamfer(sharedEdges, length = 8, length2 = 3.99999, reference = targetZFace[zIndicies[i]])
            if diagnosticMode == 1:
                show(faceList[vIndicies[i]], targetZFace[zIndicies[i]])
                time.sleep(smallDiagnosticTime)
            
    basisCylinderModified = input

    if diagnosticMode == 1: 
        show(basisCylinderModified)
        time.sleep(largeDiagnosticTime)

    # BasisCylinder merger, we're taking the modified basis cylinder and adding the 45 degree screw holes to it, which have been modified to subtract clearance cylinders if they intersect with them.

    with BuildPart() as basisCylinder:
        add(basisCylinderModified)
        add(finalScrewHoles)

    if diagnosticMode == 1: 
        reset_show()
        show_object(basisCylinder, name = "basisCylinder")
        time.sleep(largeDiagnosticTime)

    totalTime = time.perf_counter() - startTime

    if diagnosticMode == 1 or diagnosticMode == 2:
        print(totalTime)

    return(basisCylinder)



