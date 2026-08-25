from build123d import *
from ocp_vscode import *
import cadquery as cq
import time
import math
import sys

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