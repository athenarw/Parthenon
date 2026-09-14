from build123d import Cylinder
from build123d import *
from ocp_vscode import *
import cadquery as cq
import time
import math
import sys
from dataclasses import dataclass, field
import bd_warehouse.thread, bd_warehouse.fastener 
from pathlib import Path
from sympy import false
from casadi import diag
from build123d.topology.composite import Part
import yaml

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
        keyLoft = findY
    elif z == 0: 
        keyLoft = findX
    elif z == 2: 
        keyLoft = findZ

    loftRotationVector = (0,0,1)
    loftRotationAngle = 180

    target_face1 = min(x.faces(), key=keyLoft)
    target_face2 = max(y.faces(), key=keyLoft)

    wire1 = target_face1.outer_wire()
    wire2 = Wire(list(reversed([e.reversed() for e in target_face2.outer_wire().edges()])))
    part_rotated = Part(Compound([Solid.make_loft([wire1,wire2])]).wrapped)
    """
    part = loft([target_face1,target_face2])
    part_rotated = part.rotate(
            axis = Axis(part.center(), loftRotationVector),
            angle = loftRotationAngle
        )
    """
    return part_rotated

# need to make this rotatable with our metaphorical theta quantity for arbor rotation
# Function for building positional arms
# This function currently is set up to only really produce arms for 4 sites at a time.
# in the event we want variable site populations, we might want to rework some of this.  
def armConstructor(i,x,z,mirrorNub,cylinderOuterRadius=18,cylinderInnerRadius=15,cylinderInnermostRadius=13.75,diagnosticMode=0,largeDiagnosticTime=0.5,smallDiagnosticTime=0.1): # i = nub index, x = nub, z = shaft upper boundary plane, cylinderRadius is the OD of the basis cylinder for this chamber

    # Universal internal properties
    armClearance = (9.76 + 2) / 2 # This is the distance an arm needs from the its site.plane.origin.X in x in order for the arm to be acceptably placed
    cylinderAttachmentPointZDisplacement = 2.5 # the distance "down" in Z from the top of the cylinder to the top of the arm
    cylinderAttachmentPointYThickness = 2.0 # Arm thickness in Y
    armXThickness = 2.0 # Arm thickness in X

    # This is a small rectangle appended to the side of the outer rectangle which homes the loft. It is NOT a cube. :)
    homingCubeHeight = 2.5 # Presently set equal to the nub height
    homingCubeWidth = 0.6 # Must be greater than the fillet size below
    homingCubeDepth = cylinderAttachmentPointYThickness 

    # Vectors
    armDuplicatorVector = (0,0,1) # this just rotates around the z axis
    armDuplicatorAngle = 180 # By 180 degrees. It's for mirroring the arms we build. 

    # this is the if-then that governs the offset we use for the attachment points, so that the furthest-out edge in x determines 
    # ...the attachment point location, rather than the innermost side. 
    if z.origin.Y < 0:
        yThickness = -1 * cylinderAttachmentPointYThickness
    elif z.origin.Y == 0:
        yThickness = 0
    elif z.origin.Y > 0:
        yThickness = cylinderAttachmentPointYThickness

    # Attachment point mathematics! Thickness of the cylinder at a given point in y is computable as the x value at that y of the inner and outer circles
    outerRadiusX = math.sqrt(cylinderOuterRadius**2 - (z.origin.Y + yThickness/2)**2)
    innerRadiusX = math.sqrt(cylinderInnermostRadius**2 - (z.origin.Y + yThickness/2)**2)
    cylinderAttachmentPointArmLength = outerRadiusX - innerRadiusX + 0.5 # 0.25 is offset for fillets
    """
    mpx = 1 # This is a static stopgap; these can be scaled the same way the start coordinates are being scaled
    # Outside arms 
    if i == 0 or i == 3:
        cylinderAttachmentPointXDisplacement = 13 # Closer to x = 0 than the middle arms.
        cylinderAttachmentPointArmLength = (cylinderOuterRadius - cylinderInnermostRadius + 0.8)*mpx # length of initial horizontal portion of the arm

    # Middle arms 
    if i == 1 or i == 2:
        cylinderAttachmentPointXDisplacement = 14 # further from x = 0 than the outside arms
        cylinderAttachmentPointArmLength = (cylinderOuterRadius - cylinderInnermostRadius + 0.8)*mpx # This is the length of the initial horizontal portion of the arm
    1.06

    """


    # each arm is one outer rectangle with an inner rectangle subtracted from it.
    # This is the outer rectangle math. Width is in the x direction, Height is in the Z direction. 
    outerRectangleWidth = cylinderAttachmentPointArmLength + armXThickness #
    outerRectangleHeight = 0 - z.origin.Z - cylinderAttachmentPointZDisplacement + 2.5

    # Inner rectangle, will be subtracted from the outer rectangle
    innerRectangleWidth = outerRectangleWidth - armXThickness
    innerRectangleHeight = outerRectangleHeight - cylinderAttachmentPointZDisplacement

    # we need some circle math to properly home the arms
    # The below pulls the OD of the basisCylinder and the site Y coordinate. 
    # Then it homes the x coordinate to the maximum available starting value on the circle, 
    # With an offset to accomodate the thickness of the actual arm itself. 
    # Okay before this leaves my short term memory let's talk about this. 
    # you have a point p somewhere on a circle of r. you have p.Y and p.X. 
    # You want the two points inscribed by the circle at p.Y., relative to p.
    # These are going to be: [(r^2 - p.Y^2)^(1/2) + p.X, p.Y] and [(r^2 - p.Y^2)^(1/2) - p.X, p.Y]
    # Use the first for the primary arm and the second for the mirror arm.
    
    armXStartCoordinate = math.sqrt(cylinderOuterRadius**2 - (z.origin.Y + yThickness/2)**2) - 0.15; """+ armXThickness/2"""
    """
    armXStartCoordinatePart2 = z.origin.X
    if armXStartCoordinatePart1 > armXStartCoordinatePart2:
        armXStartCoordinate = armXStartCoordinatePart1
    else:
        armXStartCoordinate = armXStartCoordinatePart2
    """
    
    armXMirrorCoordinate = armXStartCoordinate
    """math.sqrt(cylinderOuterRadius**2 - (z.origin.Y + yThickness)**2)  - z.origin.X - shaftandnubhalved"""
    if diagnosticMode == 1:
        print(armXStartCoordinate)
        print(armXMirrorCoordinate)

    # Here we are building vectors to move our rectangle primitives around. 
    outerRectangleTranslationVector = (-armXStartCoordinate + outerRectangleWidth/2, z.origin.Y + cylinderAttachmentPointYThickness/2, -cylinderAttachmentPointZDisplacement - outerRectangleHeight/2)
    innerRectangleTranslationVector = (-armXStartCoordinate + innerRectangleWidth/2, z.origin.Y + cylinderAttachmentPointYThickness/2,  -cylinderAttachmentPointZDisplacement - innerRectangleHeight/2 - (outerRectangleHeight - innerRectangleHeight))
    homingCubeTranslationVector = (-armXStartCoordinate + homingCubeWidth/2 + outerRectangleWidth, z.origin.Y + homingCubeDepth/2,  -cylinderAttachmentPointZDisplacement - homingCubeHeight/2 - (outerRectangleHeight - homingCubeHeight))
    mirrorFlipVector = (armXStartCoordinate - outerRectangleWidth/2, 0, 0)

    # Generating arm components
    outerCubeUnmoved = generateCube(outerRectangleWidth,cylinderAttachmentPointYThickness,outerRectangleHeight)
    innerCubeUnmoved = generateCube(innerRectangleWidth,cylinderAttachmentPointYThickness,innerRectangleHeight)
    homingCubeUnmoved = generateCube(homingCubeWidth,homingCubeDepth,homingCubeHeight)

    # translating the arm components 
    outerCube = moveMe(outerCubeUnmoved, outerRectangleTranslationVector)
    innerCube = moveMe(innerCubeUnmoved,innerRectangleTranslationVector)
    homingCube = moveMe(homingCubeUnmoved, homingCubeTranslationVector)

    mirrorIterator = 0

    # Constructing final part
    with BuildPart() as arm1InProgress:
        add(outerCube)
        add(homingCube)
        add(innerCube, mode=Mode.SUBTRACT)

    # Now we fillet, we've made the homingCube longer so we can do this step more easily. 
    # fillet-ing final part for those bits which may be filleted internally
    input = arm1InProgress
    inputStored = input
    armTest = arm1InProgress
    xEdges = [1,2,2,1]
    zEdges = [0,1,3,2]
    rads: list = [2.5,0.5,0.5,0.5]
    for b, edge in enumerate(xEdges):
        input = filletMe(input,edge,zEdges[b],rads[b])

    coordinateComparator = input
    # Pull mininum and maximum x values from the arm shape
    minX = coordinateComparator.bounding_box().min.X
    maxX = coordinateComparator.bounding_box().max.X

    # If the x values are too close to the plane origin, they skip adding that arm; this prevents collision with the arbor. 
    if abs(minX - z.origin.X) < armClearance or abs(maxX - z.origin.X) < armClearance:
        with BuildPart() as arm1:
            pass

    else:
        # Lofts - this is lofting the homing rectangle to a nub. 
        loft1 = loftMe(x, homingCube, 0) 
        with BuildPart() as arm1:
            add(input)
            add(loft1)


    # arm rotator and duplicator (mirror engine)
    mirrorTranslateVector = (armXMirrorCoordinate - outerRectangleWidth/2)

    arm2inProgress = input.translate(
        mirrorFlipVector).rotate(
        axis = Axis(Vector(0,z.origin.Y,z.origin.Z), armDuplicatorVector),
                    angle = armDuplicatorAngle
    ).translate(
        mirrorTranslateVector
    )

    homingCubeMirror = homingCube.translate(
        mirrorFlipVector).rotate(
        axis = Axis(Vector(0,z.origin.Y,z.origin.Z), armDuplicatorVector),
                    angle = armDuplicatorAngle
    ).translate(
        mirrorTranslateVector
    )

    coordinateComparator2 = arm2inProgress
    # Pull mininum and maximum x values from the arm shape
    minX = coordinateComparator2.bounding_box().min.X
    maxX = coordinateComparator2.bounding_box().max.X

    # If the x values are too close to the plane origin, they skip adding that arm; this prevents collision with the arbor. 
    if abs(minX - z.origin.X) < armClearance or abs(maxX - z.origin.X) < armClearance:
        with BuildPart() as arm2:
            pass
    else: 
        # Lofts - this is lofting the homing rectangle to a nub. 
        loft2 = loftMe(mirrorNub, homingCubeMirror, 0) 
        # Constructing final part
        with BuildPart() as arm2:
            add(arm2inProgress)
            add(loft2)

    if diagnosticMode == 1:
        show(homingCubeMirror, arm1)
        time.sleep(largeDiagnosticTime)

    if diagnosticMode == 1:
        show(arm2, arm1)
        time.sleep(largeDiagnosticTime)

    return (arm1,arm2,armTest)

def chamberCylinder(chamberIdentity, diagnosticMode,smallDiagnosticTime=0.1,largeDiagnosticTime=0.5):

    # Timer for keeping track of how long the basis cyinder takes to make
    startTime = time.perf_counter()


    # This is a function which builds our basisCylinder. 
    # To start with, we need a chamberIdentity to know the parameters of the basisCylinder we are going to build.
    # Then we load our config file for that chamber and resolve it into a dataclass.
    configPath = Path(__file__).parent.parent / "chamberConfigs" / f"{chamberIdentity}.yaml"
    if not configPath.exists():
        raise ValueError(f"No config found for this chamber identity: '{chamberIdentity}.'")

    with open(configPath) as f:
        config = yaml.safe_load(f)

    # Parameters for cylindrical shapes for the basis cylidner
    chamberRadius1 = config["chamberRadius1"]
    chamberRadius2 = config["chamberRadius2"]  # 0.025mm thicken step in arbor npx backbone. built in here to the radius
    chamberRadius3 = config["chamberRadius3"]
    chamberGripOuterHeight = config["chamberGripOuterHeight"]
    chamberGripInnerHeight = config["chamberGripInnerHeight"]

    # Cutaway triangle parameters
    cutTrianglePrimaryAngle = config["cutTrianglePrimaryAngle"]  # This is the cutout angle in the basis cylinder
    cutTriangleSecondaryAngle = config["cutTriangleSecondaryAngle"]  # This is the cutout angle relative to the topmost throughhole axis
    cutTriangleHeight = config["cutTriangleHeight"]
    triangleAngle = config["triangleAngle"]
    triangleThickness = config["triangleThickness"]
    vertices1 = tuple(config["vertices1"])

    # Throughhole parameters
    throughHoleAngle = config["throughHoleAngle"]  # This is the angle between the throughholes
    throughHoleRadius = config["throughHoleRadius"]  # This is toleranced for a 4-40 screw. Note: This needs to be used for Goliath Posterior
    throughHoleRadius2_56 = config["throughHoleRadius2_56"]  # This is toleranced for a 2-56 screw. Note: This is for both of Malachi's chambers, and for Goliath Anterior.
    clearanceRadius = config["clearanceRadius"]  # This is to allow for socket caps to clear the 45 degree bits on the sides of the basis cylinder.

    # Directional indicator triangle parameters
    indicatorTriangleSideLength = config["indicatorTriangleSideLength"]
    indicatorTriangleInternalAngles = config["indicatorTriangleInternalAngles"]
    indicatorOffset = config["indicatorOffset"]
    indicatorHorizontalDisplacement = config["indicatorHorizontalDisplacement"]
    indicatorTriangleThickness = config["indicatorTriangleThickness"]

    # Values calculated from the config values above (not themselves stored in the config)
    vertices2 = (-2*chamberRadius3, 0, 0)
    vertices3 = (-3*chamberRadius3*(math.cos(math.radians(triangleAngle))), -3*chamberRadius3*(math.sin(math.radians(triangleAngle))), 0)
    indicatorTriangleAngle = -1 * (33.456000 + throughHoleAngle)
    indicatorTotalYDisplacement = indicatorHorizontalDisplacement + indicatorOffset + (chamberRadius3 - chamberRadius1)/2
    
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
    """
    secondChamfer = newChamferedCube.edges().filter_by(GeomType.LINE).filter_by(lambda shape: shape.center().Z > -.1).filter_by(lambda shape: abs(shape.length - 3) < 1e-6)

    secondChamferedCube = chamfer(secondChamfer, length = 0.5)
    """
    filletedCubeEdges = newChamferedCube.edges().filter_by(GeomType.LINE).filter_by(lambda shape:  shape.center().Z < -1).filter_by(lambda shape: abs(shape.length) > 2)

    if diagnosticMode == 1:
        show(filletedCubeEdges)
        time.sleep(largeDiagnosticTime)

    filletedCube = fillet(filletedCubeEdges, radius = 0.25)

    # Translation and rotation vectors
    cubeTranslationVector = (cubeXDisplacement, cubeYDisplacement, cubeZDisplacement)
    cubeRotationVector = (0,0,1)

    newChamferedCubeWithScrewHole = filletedCube - threadedInsertRotated

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
                if overlap is not None and overlap.volume > 1e-9 and diagnosticMode == 1:
                    print(f"Cube {i} intersects with Clearance Cylinder {j}.")
                elif diagnosticMode == 1:
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

    with BuildPart() as basisCylinderPreWork:
        add(basisCylinderModified)
        add(finalScrewHoles)

    #filleting and chamfering some edges
    filletEdgesBasisCylinderAndFinalScrewHoles = new_edges(
        finalScrewHoles, 
        basisCylinderModified, 
        combined = basisCylinderPreWork.part).filter_by(
            GeomType.LINE)
    basisCylinderAlmost = fillet(filletEdgesBasisCylinderAndFinalScrewHoles, radius = 0.25)

    """
    secondChamfer = newChamferedCube.edges().filter_by(GeomType.LINE).filter_by(lambda shape: shape.center().Z > -.1).filter_by(lambda shape: abs(shape.length - 3) < 1e-6)

    secondChamferedCube = chamfer(secondChamfer, length = 0.5)
    """

    additionalFilletEdges = basisCylinderAlmost.edges().filter_by(GeomType.CIRCLE).filter_by(lambda shape: abs(shape.radius - chamberRadius3) < 1e-6).filter_by(lambda shape: shape.center().Z > -0.1)
    moreFilletEdges = basisCylinderAlmost.edges().filter_by(GeomType.LINE).filter_by(lambda shape: shape.center().Z > -.1).filter_by(lambda shape: shape.length > 1.7).filter_by(lambda shape: shape.length < 1.8)
    filletEdgesODBasisCylinder = additionalFilletEdges + moreFilletEdges
    if diagnosticMode == 1: 
        show(filletEdgesODBasisCylinder)
    basisCylinder = chamfer(filletEdgesODBasisCylinder, length = 0.25)

    if diagnosticMode == 1: 
        reset_show()
        show_object(basisCylinder, name = "basisCylinder")
        time.sleep(largeDiagnosticTime)

    totalTime = time.perf_counter() - startTime

    if diagnosticMode == 1 or diagnosticMode == 2:
        print(totalTime)

    return(basisCylinder)


# meshPlanes function - input: chamberIdentity, points2D, ZOffset(change this!)
# this will be an if statement based on a chamber input field. That field will also need to adjust the basis cylinder we generate 
# Notes for future development:
# possibility: Using a bounding circle to remove the vertical triangles on the sides of the mesh, in order to reduce triangle count and increase speed - backburnered. use trimesh?
# Probably need to integrate coordinates from SPOTS somehow. Likely, also need a least-squares fit line for the arbor, and some parameter permutation if we want a normal offset from the arbor line. 


def meshPlanes(chamberIdentity, points2D, ZOffset = 2, shaftDiameter = 3.85, shaftHeight = 4, 
               diagnosticMode = 2, largeDiagnosticTime = 0.5, smallDiagnosticTime = 0.1): 
    # Importing reference chamber mesh - Goliath Posterior V3 starting V3:
    if chamberIdentity == "GoliathPosterior":
        meshName = "chamberMoldMeshGoliathPosteriorV3.stl"
    else:
        print("ERROR: INCOMPATIBLE CHAMBER IDENTITY. PLEASE REFACTOR INPUT.")

    # Path
    meshPath = Path(__file__).parent.parent / meshName

    # meshName is going to be input from either a user field or from a chamber object which is input from a user field. either way this is close to the origin of the object, so it is upstream of lots of things. 
    chamberMoldCachePath = meshPath.with_suffix(".brep")

    if chamberMoldCachePath.exists():
        chamberMold = import_brep(chamberMoldCachePath)
    else:
        chamberMold = Mesher().read(meshName)[0]
        export_brep(chamberMold,chamberMoldCachePath)

    # NOTE: MESHES CANNOT BE TRANSLATED. TRANSLATE OTHER OBJECTS AROUND THEM.

    # Displaying the mesh and the cylinder both for diagnostics
    if diagnosticMode == 1:
        show_object(chamberMold, name = "chamberMold")
        print(chamberMoldCachePath)
        time.sleep(largeDiagnosticTime)

    # Retrieving / generating points for probe penetration:
    # Initializing parameters
    meshZ = -5
    GTShaftID = 0.675
    recessDiameter = 3.1
    GTShaftOD = 4
    points3D = []
    circularLocations = []

    # Appends a Z value to each of the 2D points
    for i, x in enumerate(points2D):
        points3D.append(x + (meshZ,))

    # OD Sketch at the points3D location.
    for x in points3D:
        with BuildSketch() as sk:
                with Locations(x):
                    Circle(radius = GTShaftOD/2, align=None)
        circularLocations.append(sk)

    # Diagnostics for previous step
    if diagnosticMode == 1: 
        show_object(circularLocations, name = "transient")
        print(circularLocations)
        time.sleep(largeDiagnosticTime)

    # Projects circles down onto the mesh surface and adds interfaces onto list
    projectedCurves = []
    for x in circularLocations:
        wire = x.sketch.faces()[0].outer_wire()
        hits = wire.project_to_shape(chamberMold,direction=(0,0,-1))
        projectedCurves.append(hits)

    # Diagnostics for previous step
    if diagnosticMode == 1: 
        print(projectedCurves)
        show_object (projectedCurves, name = "transient", update = True)
        time.sleep(largeDiagnosticTime)

    # Initializes list of faces
    frameFaces = []

    # Construct faces from center point of each projected curve, using the slope at that location on the chamber mesh.
    for x in circularLocations:
        face = x.sketch.faces()[0] 
        center = face.center() # Finds center point
        axis = Axis((center.X, center.Y, chamberMold.bounding_box().max.Z), (0,0,-1))
        point, normal = chamberMold.find_intersection_points(axis)[-1]
        tiltedPlane = Plane(origin=point, z_dir = normal)
        frameFaces.append(face.located(Location(tiltedPlane)))

    # Diagnostics for previous step
    if diagnosticMode == 1: 
        print(frameFaces)
        show_object (chamberMold, name = "chamberMold", mode = Render.NONE, update = True)
        show_object (frameFaces, name = "transient", update = True)
        time.sleep(largeDiagnosticTime)


    # Offsetting the projected curve faces to provide targets for extrusion limits
    # This allows 2mm of space between the tissue surface and the the bottom of the shafts

    # Initializing parameters offset frame faces
    offsetFrameFaces = []
    zPlanarOffset = ZOffset  # Hardlined offset. Currently static, could be good to transform into a variable in the long run.

    # Changing faces to planes, offsetting them 2mm from the mesh surface for gap region
    for x in frameFaces:
        plane1 = Plane(x)
        offsetPlane = Plane(origin = plane1.origin + (0,0,zPlanarOffset), x_dir=plane1.x_dir, z_dir = plane1.z_dir)
        offsetFrameFaces.append(offsetPlane)

    # Diagnostics for previous step
    if diagnosticMode == 1: 
        print(offsetFrameFaces)
        show_object (offsetFrameFaces, name = "transient", update = True)
        time.sleep(largeDiagnosticTime)

    # Initializing parameters for bottomSurfaceSolids and startingOffsetPlanes, our outputs for this function
    startingOffsetPlanes = []

    # Offsets planes by the shaftHeight so we have a starting location for extrusion
    for x in offsetFrameFaces: # These are actually planes, not faces
        appendMe = Plane(origin = x.origin + (0,0,shaftHeight), x_dir = (1,0,0), z_dir = (0,0,1))
        startingOffsetPlanes.append(appendMe)

    # Initializing solids list for export later
    bottomSurfaceSolids = []

    # Generating solids from bottom surface planes for later use.
    for x in offsetFrameFaces:
        with BuildPart() as cyl:
            with BuildSketch(x):
                Circle(radius = shaftDiameter)
            extrude(amount=1)
        bottomSurfaceSolids.append(cyl.part)

    # Diagnostics for previous steps
    if diagnosticMode == 1: 
        print(startingOffsetPlanes,bottomSurfaceSolids)
        show_object (startingOffsetPlanes, name = "transient", update = True)
        time.sleep(largeDiagnosticTime)
        show_object (bottomSurfaceSolids, name = "transient", update = True)
        time.sleep(largeDiagnosticTime)

    return(points3D, bottomSurfaceSolids, startingOffsetPlanes)


def shaftConstructor(startingOffsetPlanes, bottomSurfaceSolids, innerShaftDiameter = 0.675000, shaftDiameter = 4, diagnosticMode = 0, largeDiagnosticTime = 0.5, smallDiagnosticTime = 0.1):

    # Builds circles on the projected curves and constructs shafts

    # Initialize parameters
    shaftList = []
    throughHoles = []
    shaftListWithThroughHoles = []
    seams = []
    shaftRadius = shaftDiameter/2
    innerShaftRadius = innerShaftDiameter/2
    j = 0

    # Iterate through all the sites and construct initial shaft geometry
    for i, x in enumerate(startingOffsetPlanes): 
        # First build the outer shaft
        with BuildPart() as shaft:
            with BuildSketch(x) as sk:
                Circle(radius=shaftRadius)
            extrude(until=Until.NEXT, target = bottomSurfaceSolids[i], dir=(0,0,-1))
        shaftList.append(shaft)

        # Next build the throughhole
        with BuildPart() as throughhole:
            with BuildSketch(x) as sk:
                Circle(radius = innerShaftRadius)
            extrude(until = Until.NEXT, target = bottomSurfaceSolids[i], dir=(0,0,-1))
        throughHoles.append(throughhole)

        # Now subtract the throughhole geometry from the shaft geometery
        with BuildPart() as shaftWithThroughHole:
            add(shaftList[i])
            add(throughHoles[i], mode = Mode.SUBTRACT)
        shaftListWithThroughHoles.append(shaftWithThroughHole)

    # Diagnostics for previous step
    if diagnosticMode == 1: 
        print(startingOffsetPlanes,bottomSurfaceSolids)
        show_object (shaftList, name = "shaftList", update = True)
        time.sleep(largeDiagnosticTime)
        show_object (throughHoles, name = "transient", update = True, options={"color": (255, 0,0)})
        time.sleep(largeDiagnosticTime)

    # Initialize parameters and lists for this step
    targetFaces = []
    filletItems = []
    targetEdgesMasterList = []

    # Fillet slanted bottom edge of shaft and throughhole
    for i, x in enumerate(shaftListWithThroughHoles):
        targetEdges = [] 
        targetFace = min(shaftListWithThroughHoles[i].faces(), key = findZ) # Grabs the bottom face in Z
        targetFaces.append(targetFace) # adds that face to a list
        targetEdge1, targetEdge2 = targetFace.edges() # This grabs the ID and OD at the bottom face in Z
        targetEdges.append(targetEdge1) # Appends these to lists
        targetEdges.append(targetEdge2)
        filletItem: Sketch | Part | Curve = fillet(targetEdges, radius = 0.20) # fillets at 0.20 mm. Could break code if we change the shaft ID and OD too much.
        filletItems.append(filletItem)
        targetEdgesMasterList.append(targetEdges) # Storage list 

    # Saving for easy access in next step  - this references the same list rather than creating a clone, possibly change
    shaftListWithThroughHolesFilleted = filletItems

    # Diagnostics for previous step
    if diagnosticMode == 1: 
        print(targetEdges,shaftListWithThroughHolesFilleted)
        show_object (targetEdgesMasterList, name = "transient", update = True)
        time.sleep(largeDiagnosticTime)
        show_object (shaftList, name = "shaftList", mode = Render.NONE, update = True)
        show_object (shaftListWithThroughHolesFilleted, name = "transient", update = True)
        time.sleep(largeDiagnosticTime)

    # Fillet-ing top edge of throughholes:

    # Initialize parameters
    filletList = []

    # For each shaft, find the edge which corresponds to the ID at the top side of the shaft
    for i, x in enumerate(shaftListWithThroughHolesFilleted):
        edge = x.edges().filter_by(GeomType.CIRCLE).filter_by(
            lambda a: abs(a.radius - innerShaftRadius) < 1e-6)
        seams.append(edge) # And append this edge to a list of edges

        # Now fillet this edge at 0.25mm, could break code if we mess with OD and ID too much.
        filletObject = fillet(edge, radius = 0.25)
        filletList.append(filletObject) # And add to list for storage

    # Diagnostics for previous step
    if diagnosticMode == 1:
        show(filletList)

    # Saving for easy access - this references the same list rather than creating a clone, possibly change
    shaftListWithThroughHolesFilletedTwice = filletList

    # Display everything for the purpose of sanity checks - completed shaft list
    if diagnosticMode == 1: 
        show(shaftListWithThroughHolesFilleted)

    return shaftListWithThroughHolesFilletedTwice

# Nubs. These are arrayed around the shafts, and provide targeting surfaces for the arms to loft to.
# Doing this a little bit differently from Anna's Onshape. Instead of building in the default plane, I'm going to build each set of nubs on the top plane of the actual shaft it's attached to.
def nubConstructor(startingOffsetPlanes, diagnosticMode = 0, largeDiagnosticTime = 0.5, smallDiagnosticTime = 0.1):

    # Initializing some parameters - a fair bit of static geometry here, might want to dynamicize at a later date
    parallelNubSeparation = 2.64575
    nubLongSide = 3
    nubShortSide = 1.35425
    nubDepth = 2.5
    nubsList = []
    rotatorLocations = [1,2,3,4]
    rotatorAngle = 90
    nubTemplates = []
    nubTemplatesFlattened = []
    nubDisplacementVector = (0,parallelNubSeparation/2 + nubShortSide/2,0)
    nubRotationVector = (0,0,1)

    # Iterate through starting planes, generating four nubs per plane and rotating them to be at right angles, surrounding their shaft.
    for i, x in enumerate(startingOffsetPlanes):
        for k, j in enumerate(rotatorLocations):
            # Generate nub at origin, then move
            nubTemplate = Rectangle(nubLongSide,nubShortSide).located(Location(startingOffsetPlanes[i])).translate(nubDisplacementVector).rotate(
                axis = Axis(startingOffsetPlanes[i].origin, nubRotationVector),
                angle = rotatorAngle*k
            )
            nubTemplates.append(nubTemplate)

            # Build the nub and append it to storage list
            with BuildPart() as nubs:
                extrude(nubTemplate, amount=nubDepth, dir = (0,0,-1))
            nubsList.append(nubs.part)

    # Flattens nubs to xy plane - feeds into loftConstructor function later and is used to join nubs together
    for i, x in enumerate(nubTemplates):
        nubTemplatesFlattened.append(flattenToXY(nubTemplates[i]))

    # Diagnostics for previous step
    if diagnosticMode == 1:
        show(nubsList)

    # Outputs
    return(nubsList, nubTemplatesFlattened)

# loftConstructor function
# inputs: nubTemplatesFlattened, nubsList
def loftConstructor(nubsList, nubTemplatesFlattened, startingOffsetPlanes, diagnosticMode = 0, largeDiagnosticTime = 0.5, smallDiagnosticTime = 0.1):

    overlaps = []

    # Overlap areas between nubs 2,4
    overlaps.append(nubTemplatesFlattened[2] & nubTemplatesFlattened[4])

    # Overlap areas between nubs 6,8
    overlaps.append(nubTemplatesFlattened[6] & nubTemplatesFlattened[8])

    # Overlap areas between nubs 8,10
    overlaps.append(nubTemplatesFlattened[10] & nubTemplatesFlattened[12])


    # Constructing overlap solids, pruning union parts between different shafts

    overlapSolids = []
    prunedParts = []
    lofts = []
    arbitraryOverlapHeight = 5



    # Generating overlap structures
    for i, x in enumerate(overlaps):
        with BuildPart() as firstpart:
            extrude(overlaps[i], amount = arbitraryOverlapHeight*10, dir = (0,0,-1))
            overlapSolids.append(firstpart.part)

    # Deleting overlap between shafts 1 and 2, numbered from +y to -y in global coordinates
    with BuildPart() as pt:
        add (nubsList[2])
        if overlapSolids[0] is not None:
            add (overlapSolids[0], mode = Mode.SUBTRACT)
        prunedParts.append(pt.part)

    with BuildPart() as pt:
        add (nubsList[4])
        if overlapSolids[0] is not None:
            add (overlapSolids[0], mode = Mode.SUBTRACT)
        prunedParts.append(pt.part)

    loft1 = loftMe(nubsList[2], nubsList[4])
    lofts.append(loft1)

    # Deleting overlap between shafts 10 and 12, numbered from +y to -y in global coordinates
    with BuildPart() as pt:
        add (nubsList[10])
        if overlapSolids[2] is not None:
            add (overlapSolids[2], mode = Mode.SUBTRACT)
            
        prunedParts.append(pt.part)

    with BuildPart() as pt:
        add (nubsList[12])
        if overlapSolids[2] is not None:
            add (overlapSolids[2], mode = Mode.SUBTRACT)
        prunedParts.append(pt.part)

    loft2 = loftMe(nubsList[10], nubsList[12])
    lofts.append(loft2)

    with BuildPart() as pt:
        if startingOffsetPlanes[1].origin.Z > startingOffsetPlanes[2].origin.Z:
            add (nubsList[6])
        elif startingOffsetPlanes[1].origin.Z < startingOffsetPlanes[2].origin.Z:
            add (nubsList[8])
        else:
            add (nubsList[6])
            add (nubsList[8])
        if overlapSolids[1] is not None:
            add(overlapSolids[1], mode=Mode.SUBTRACT)

        prunedParts.append(pt.part)
        
    loft3 = loftMe(nubsList[6], nubsList[8])

    if diagnosticMode == 1: 
        show(prunedParts, colors=["#e8b024", "#e8b024", "#e8b024",  "lightblue"])
        len(prunedParts)
        time.sleep(largeDiagnosticTime)

    return(prunedParts, lofts, overlapSolids)

def armStreamConstructor(startingOffsetPlanes,nubsList,handPickedIndicies,diagnosticMode = 0, largeDiagnosticTime = 0.5, smallDiagnosticTime = 0.1):
    # This is basically a wrapper around armConstructor which applies armConstructer to an entire list.

    # Initializing and resetting lists
    testArms = []
    outputArmStream = []
    refinedNubsList = [nubsList[i] for i in handPickedIndicies]
    mirrorNubsList = [nubsList[i + 2] for i in handPickedIndicies]

    # Calls armConstructor for each site, although this is before sites are a thing. Perhaps reverse this order?
    for i, x in enumerate(refinedNubsList):
        arm1, mirrorArm,armTest = armConstructor(i, refinedNubsList[i],startingOffsetPlanes[i], mirrorNubsList[i], diagnosticMode = diagnosticMode)
        outputArmStream.append(arm1)
        outputArmStream.append(mirrorArm)
        testArms.append(armTest)
        # Ensure construction sketches are either nub-centric, or somehow related directionally to the rotation of the arbor centerline. 

    # Visual diagnostics for this step
    if diagnosticMode == 1:
        show(basisCylinder, shaftListWithThroughHolesFilletedTwice, nubsList, outputArmStream, colors=["#e8b024", "#e8b024", "#e8b024",  "lightblue", "pink", "pink"])

    return(outputArmStream, testArms)

def siteConstructor(Site, startingOffsetPlanes,shaftListWithThroughHolesFilletedTwice,nubsList,prunedParts,outputArmStream,diagnosticMode = 0, largeDiagnosticTime = 0.5, smallDiagnosticTime = 0.1):
    # Initialize and reset the variables used in this cell

    # Adds the x-axial nubs, the outer union parts, and the shafts to their site. 
    sites = []
    for i, plane in enumerate(startingOffsetPlanes):
        sites.append(Site(
            shaft = shaftListWithThroughHolesFilletedTwice[i],
            plane = plane,
            nubs = nubsList[i*4+1:i*4 + 4:2] + [prunedParts[i]],
            arms = outputArmStream[i*2:i*2 + 2]
        )) 
    return(sites)


# Put everything together and construct the final guide tube frame.
def guideTubeFrameConstructor(sites, basisCylinder, nubsList, prunedParts, lofts, overlapSolids, diagnosticMode = 0, largeDiagnosticTime = 0.5, smallDiagnosticTime = 0.1):

    # Initializing and resetting parameters
    fillets = []
    filletedItems = []
    combinedSitesWithArms = []
    armFillets = []
    filletParameter2 = 0



    # Picks the highest(z) starting offset plane of the two middle planes. 
    # Adds the central nub of the higher z site and appends to nubs
    # trims the central nub of the lower z site and appends that to nubs
    if sites[1].plane.origin.Z < sites[2].plane.origin.Z:
        sites[1].nubs.append((nubsList[6]))
        sites[2].nubs.append((prunedParts[-1]))
        planeHeightIndicator = 2 # this keeps track of the higher plane

    elif sites[1].plane.origin.Z > sites[2].plane.origin.Z:
        sites[2].nubs.append((nubsList[8]))
        sites[1].nubs.append((prunedParts[-1]))
        planeHeightIndicator = 1 # this keeps track of the higher plane

    # covers the case in which the zaxis is the same, in which case we just add both nubs
    else:
        sites[1].nubs.append((nubsList[6]))
        sites[2].nubs.append((nubsList[8]))

    # Visual diagnostics for this step
    if diagnosticMode == 1 or diagnosticMode == 1: 
        show(*[site.shaft for site in sites], [site.nubs for site in sites], [site.arms for site in sites], basisCylinder)



    # Iterate through sites and fuse them with their nubs. Then fillet.
    for i, site in enumerate(sites): # Iterates
        with BuildPart() as combinedSite: 
            # Add sitewise preconstructed parts
            add(site.shaft)
            add(site.nubs)

        # Grab edges for filleting
        filletMe = new_edges(
            site.shaft, 
            *site.nubs, 
            combined = combinedSite.part).filter_by(GeomType.LINE)

        # Add those edges to a list for storage
        fillets.extend(filletMe)

        # Fillet these, using a structure which adapts to unanticipated changes in radius. If this starts erroring maybe increase max iterations.
        try:
            # Find fillet radius for selected edges
            r = combinedSite.part.max_fillet(filletMe, max_iterations=25)
            if diagnosticMode == 1:
                print(f"edge: ok, max radius = {r}")
            filletParameter = min((r), 0.25)

            # Fillet the thing using the edges found above
            filletedItem = fillet(filletMe, radius = filletParameter)

        # This will throw an error if the above doesn't work.
        except Exception as err:
            if diagnosticMode == 1 or diagnosticMode == 1:
                print(f"edge: BAD — {type(err).__name__}: {err}")

        # Append these to list for storage
        filletedItems.append(filletedItem)

    # Diagnostics for this step will show items on ocpviewer and print the length of the list containing successfully merged items. 
    if diagnosticMode == 1 or diagnosticMode == 1:
        show(filletedItems)
        print(len(filletedItems))



    # Adding arms in a sitewise fashion.
    # Iterating through sites and adding arms for each of them. 
    # Will hopefully support any number of sites, but this is untested.
    for i, site in enumerate(sites): # Iterates
        with BuildPart() as combinedSiteWithArms:
            # Adding together previously constructed parts
            add(filletedItems[i]) # Previous BuildPart() construct
            add(site.arms) # sitewise arm construction

            combinedSitesWithArms.append(combinedSiteWithArms.part) # Add to a list for storage

    # Diagnostics for visualizing the arms, sites, and basisCylinder in ocpviewer.
    if diagnosticMode == 1: 
        show([combinedSitesWithArms for site in sites], basisCylinder)



    # Adding together the basisCylinder from chamberCylinder and the sitewise arms. 
    # This combines the basis cylinder constructed with chamberCylinder
    with BuildPart() as newPart:
        # Add preconstructed parts first
        add(basisCylinder) # Add basisCylinder from chamberCylinder function
        add(combinedSitesWithArms) # Add list of sites with arms

        # Now we grab edges from the combined part
        armFillet = new_edges(
            *combinedSitesWithArms,
            basisCylinder,
            combined = newPart.part).filter_by(GeomType.LINE).filter_by(lambda e: e.length >= 2.25)

        # Now we fillet those edges. We do so by the min of 0.25mm or the largest radius the smallest intersection can sustain
        try:
            r = newPart.part.max_fillet(armFillet, max_iterations=25) # Pulls the largest r that all edges can support
            if diagnosticMode == 1: # Internal diagnostics
                print(f"edge: ok, max radius = {r}")
            filletParameter2 = min((r), 0.25) # Finds min between static and max_fillet dynamic radii
            newestPart = fillet(armFillet, radius = filletParameter2) # Constructs filleted part

        # if the fillets don't work it will throw this error in diagnostic mode. 
        except Exception as err:
            if diagnosticMode == 1:
                print(f"edge: BAD — {type(err).__name__}: {err}")

    # Diagnostics for the fillets, if they don't work this will display things including the length of armFillet and the visuals in ocpviewer.
    if diagnosticMode == 1 or diagnosticMode == 1: 
        armFillet[2].length
        show(*[armFillets], newestPart)
        show(basisCylinder, combinedSitesWithArms,armFillet)



    # Add lofts, construct finalPart, which is what we export into an STL.
    # Initializing parameters
    loftFillets = [] # Zeros out the list in case it's being rerun. Also initializes.
    filletParameter3 = 0 # Zeros out list for rerunning purposes

    # Constructing finalPart
    with BuildPart() as nextPart:
        add (newestPart) # This arises from the previously called buildPart function
        add (lofts[0]) # Lofting between nubs 2 and 4
        add (lofts[1]) # Lofting between nubs 10 and 12
        if overlapSolids[1] is None: # This is making sure that there's no overlap; if there is overlap, earlier functionality will apply.
            add(lofts[2]) # Lofting between central nubs

        # Now that we've added all the solid parts, we're going to grab all the edges we need to fillet from those parts.
        loftFillet = nextPart.edges().filter_by(
            GeomType.LINE).filter_by(
            lambda e: abs(e.length - 3) < 1e-6).filter_by(
            lambda e: abs(e.position_at(0).Z - e.position_at(1).Z) < 1e-6).filter_by(
            lambda e: abs(e.position_at(0).Y - e.position_at(1).Y) < 1e-6).filter_by(
            lambda e: e.center().Z < -1)

        # Then we extend a list of fillets. This is mostly just a storage mechanism so we can access this later if we have to.
        loftFillets.extend(loftFillet)

        # Now we're going to fillet these parts. We'll use the minimum of either the max_fillet value for the smallest edge or 0.25mm.
        try:
            r = nextPart.part.max_fillet(loftFillet, max_iterations=25) # Establishing the radius
            if diagnosticMode == 1: # Internal diagnostics
                print(f"edge: ok, max radius = {r}")
            filletParameter3 = min((r), 0.25) # Finding the min between the static radius and the max radius
            finalPart = (fillet(loftFillet, radius = filletParameter3)) # Saving the final part. 

        # if that doesn't work, this prints in diagnostic mode.
        except Exception as err:
            if diagnosticMode == 1:
                print(f"edge: BAD — {type(err).__name__}: {err}")

    # This tests whether different edges have the capability to be filleted, and if so, their max radius. It also prints those fillets.
    if diagnosticMode == 1: 
        print(loftFillets) # This prints the list.

        # This iterates through the fillets - use this if your fillets are failing, it can tell you which one is not functioning. You might have to paste it into another cell.
        for i, e in enumerate(loftFillet):
            try:
                r = nextPart.part.max_fillet([e])
                print(i, "ok — max radius:", r)
            # If the edges don't function this will alert us
            except Exception as err:
                print(i, "BAD EDGE:", type(err).__name__, err)
        print(len(nextPart.part.solids()))
    if diagnosticMode == 1 or diagnosticMode == 3:
        show(finalPart)
    return(finalPart)

# Joining file names together and saving file
def saveMe(points2D,startTime,guideTubeFrame,saveyn,fileName, chamberIdentity,diagnosticMode = 0, largeDiagnosticTime = 0.5, smallDiagnosticTime = 0.1):

    # First I'm joining the coordinate names together for a uniquely identifiable string
    prefix = "-".join(str(p) for p in points2D)

    # Then we join that string together with the user-inputted file name, and give it an stl suffix
    joinMe = [chamberIdentity, prefix, fileName]
    fileNameReal = "-".join(joinMe)
    fileNameActual = Path(fileNameReal + ".stl")

    # Diagnostics if desired, to ensure file name is correct
    if diagnosticMode == 1:
        print(prefix)
        print(fileNameReal)
        print(fileNameActual)

    # Time related diagnostics
    if diagnosticMode == 1 or diagnosticMode == 2: 
        elapsedTime = time.perf_counter() - startTime
        print(elapsedTime)

    # as of 9/2/2026:
    # diagnosticMode = 0 is who knows how long because it doesn't print! 
    # diagnosticMode = 1 is 61. 1 seconds
    # diagnosticMode = 2 is 26.3 seconds, 25.5 after activating the diagnostic toggle on all show() commands. 17.3 after refining the filleting to be out of a for loop.


    # Saves file with composite file name if saving is turned on
    if saveyn == 1:
        export_stl(guideTubeFrame, fileNameActual)
        print(f"Saved as: {fileNameActual}")

    return(fileNameActual)

