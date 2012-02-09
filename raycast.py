# Wolfenstein 3-D style ray caster
# By Jozef Kolarovic, 2011

# ============= things to do! ================
# 2. Implement support for more wall textures
# 3. Implement sprite support (enemies, items, etc.)
# 4. Z-buffer (1-dimensional should be enough!)
# 5. Ceiling / floor casting (remove parallax)
# 6. Fade / fog (maybe. if this is fast enough.)
# 7. HUD / weapon overlays
# ============================================

# modules
import pygame
import math
#from numpy import *
from pygame.locals import *
from PIL import Image

import cProfile as profile

# custom modules
import castrays


# precomputed values
sinTable = []
cosTable = []
tanTable = []

angle = 0
for i in xrange(3600):
    
    rad = math.radians(angle) + 0.0001  # avoids division by zero ^_^
    sinTable.append(math.sin(rad))
    cosTable.append(math.cos(rad))
    tanTable.append(math.tan(rad))
    angle += 0.1


# angle class
class Angle:
    
    def __init__(self,a = 0):
        self.degrees = a % 360


    def __add__(self,x):
        self.degrees = (self.degrees + x) % 360
        return self

    def __sub__(self,x):
        if (self.degrees + x >= 0):
            self.degrees += x
        else:
            self.degrees = 359 + (x - self.degrees)
        return self

    def __int__(self):
        return int(self.degrees)

    def __float__(self):
        return float(self.degrees)

    def __repr__(self):
        return str(self.degrees)

    def __lt__(self,x):
        if (self.degrees < x):
            return True
        else:
            return False


# Vertex on a 2D plane -- DEPRECIATED.
class Vertex:
    def __init__(self,x = 0,y = 0):
        self.x = x
        self.y = y

        
# Contains all world cubes and sprites. possibly remove this class.
class Grid:
    cubes = []
    sprites = []


    # creates a new grid of given size^2 (unit coordinates)
    def __init__(self, numcubes = 32, cubesize = 64):

        self.cubesize = cubesize
        self.cubecount = numcubes
        
        # init cube array
        for i in xrange(numcubes):
            column = []
            for j in xrange (numcubes):
                column.append(0)
            self.cubes.append(column)

        #init 2D grid
        self.gridSize = numcubes * cubesize
        
    def setcube(self,x,y,cube):
        if (x < self.cubecount) & (y < self.cubecount):
            self.cubes[x][y] = cube
    

    # print this map in character format
    def __repr__(self):

        retVal = 'Printing grid... \n'
        for i in xrange(self.cubecount):
            for j in xrange (self.cubecount):
                retVal = retVal + str (self.cubes[i][j])
            retVal = retVal + '\n'

        return retVal

# Projection plane handles the actual drawing of a plane to screen
class ProjectionPlane:
    width = 0
    height = 0
    wallheights = []
    textures = []
    textureOffsets = []
    floorDistances = []
    floorPositions = []
    

    def __init__(self,x,y):
        self.width = x
        self.height = y

        # load wall images as pixel arrays
        self.textures.append(pygame.image.load("content/wall.png").convert())
        self.textures.append(pygame.image.load("content/greystone.png").convert())  #floor
        self.textures.append(pygame.image.load("content/woodpanel.png").convert())  #ceiling

        
        # prepare sky and floor rects (left,top,width,height)
        self.sky = pygame.Rect(0,0,self.width,self.height/2)
        self.floor = pygame.Rect(0,self.height/2,self.width,self.height/2)

        self.midheight = y / 2

        # populate display arrays
        for i in xrange(x):
            self.wallheights.append(0)
            self.textureOffsets.append(0)
            self.textures.append(0)

            temp = []
            for j in xrange(y):
                temp.append([0,0])
            self.floorPositions.append(temp)

        self.surface = pygame.Surface((self.width,self.height))
        self.floorCeilingArray = pygame.PixelArray(pygame.Surface((self.width,self.height)))

        self.floorPxArray = pygame.PixelArray(self.textures[1])
        self.ceilingPxArray = pygame.PixelArray(self.textures[2])

    # draws a new image to screen
    def drawplane(self):

        #sky and floor fills, not required when casting floors / ceilings
        #self.surface.fill((150,150,150),self.sky)
        #self.surface.fill((75,75,75),self.floor)
        
        texture = self.textures[0]

        # draw floor & ceiling
        self.surface.blit(self.floorCeilingArray.make_surface(), (0,0))

        #draw wall columns according to distances
        for x in xrange(self.width):
            column = texture.subsurface(pygame.Rect(self.textureOffsets[x],0,1,64))         # crop wall column...
            scaledColumn = pygame.transform.smoothscale(column,(2,self.wallheights[x]))     # ...scale...
            
            drawing = self.midheight - (self.wallheights[x] / 2)        # topmost wall pixel of this column 
            self.surface.blit(scaledColumn, (x,drawing))                # draw scaled wall column
            
        return self.surface

    


# Camera object upon which to project
class Camera:

    def __init__(self, xplane = 320,yplane = 200,fov = 60, xpos = 0, ypos = 0, cubesize = 64):
        self.plane = ProjectionPlane(xplane,yplane)
        self.xpos = xpos
        self.ypos = ypos
        self.angle = Angle(0)
        self.FOV = fov
        self.cubesize = cubesize
        #self.rayIncrement = float(fov) / float(xplane)
        #self.toplane = (xplane / 2) / tanTable[30 * 10]    # distance from projection plane
        self.plane.floorDistances = self.calculateFloorDistances()

    #walks forward or backpedals
    def walk(self,speed):
        self.xpos += (speed * sinTable[self.angle.degrees * 10])
        self.ypos += (speed * cosTable[self.angle.degrees * 10])
        return True

    #rotates camera
    def rotate(self,degree):
        if degree > 0:
            self.angle += degree
        else:
            self.angle -= degree

    #casts a single ray for wall collision detection - returns boolean
    def castCollisionRay(self,colrange):
        x = self.xpos + (sinTable[self.angle.degrees * 10] * colrange)
        y = self.ypos + (cosTable[self.angle.degrees * 10] * colrange)

        return (grid.cubes[int(x/64)][int(y/64)] == 0)


    # computes distance values for every horizontal scanline - this only needs to be done once!
    def calculateFloorDistances(self):
        degrees = Angle(90.001)                        # begin with the centre of the screen
        floorScreenHeight = int(self.plane.height / 2)
        increment = float(self.FOV) / float(floorScreenHeight)

        floorDistances = []
        ceilDistances = []
        allDistances = []

        for i in xrange(floorScreenHeight):
            x = 0                       # might as well be 0 :)
            y = 77.5                    # camera height (too low moves towards camera relative to walls. too high moves away.)
                                        # camera height depends on resolution!! (h / w?)
            
            searching = True
            while (searching):

                if (y <= 0):            # floor hit, calc distance
                    distance = math.sqrt(math.pow(x,2) + math.pow(y,2))
                    beta = math.cos(math.radians(100 - degrees.degrees)) # correct fishbowl
                    distance /= beta
                    floorDistances.append(int(distance))
                    
                    searching = False

                if (x > 9999):
                    floorDistances.append(int(9999))
                    searching = False

                x = x + math.sin(math.radians(degrees))
                y = y + math.cos(math.radians(degrees))

            degrees += increment

        # organise ditance lists to match screen coordinates - easier to use this way :)
        floorDistances.reverse()
        allDistances.extend(floorDistances)
        floorDistances.reverse()
        allDistances.extend(floorDistances)

        return allDistances
            

    # cast all walls and floors
    def rayCastAll(self):

        results = castrays.raycastAll(self.xpos,self.ypos,self.angle)       # carry out all raycasting...

        # ...collect results from module
        self.plane.wallheights = results[0]         
        self.plane.textureOffsets = results[1]
        # optimise!!
        self.plane.floorCeilingArray = castrays.getFloorCeilArray(self.plane.floorCeilingArray)


# reads .png map images with which to populate a grid
def readImage(filename,grid,camera):
    image = Image.open(filename)
    mapsize = 0
    if (image.size[0] == image.size[1]):    # only squared images accepted
        mapsize = image.size[0]
        grid.cubesize = 64
        # prepare walls
        for i in xrange(mapsize):
            for j in xrange (mapsize):
                pixel = image.getpixel((i,j))
                if (pixel == (255,255,255)):        # default wall
                    grid.setcube(i,j,1)
                else:
                    grid.setcube(i,j,0)       # empty / sprite cell
                    if (pixel == (255,0,0)):        # player start
                        camera.xpos = (i * grid.cubesize) + (grid.cubesize / 2)
                        camera.ypos = (j * grid.cubesize) + (grid.cubesize / 2)
   

width = 400
height = 300
cubesize = 64

moveSpeed = 15
turnSpeed = 10
clipDistance = 50

grid = Grid()


# Init. and run main loop...
def main():
    flags = DOUBLEBUF
    screen = pygame.display.set_mode((width,height),flags,32)
    camera = Camera(width,height)
    readImage("content/map1.png",grid,camera)

    # prepare raycasting module
    castrays.init(width,height,camera.FOV,grid.cubes,camera.plane.floorDistances)
    castrays.setFloorCeilTextures(camera.plane.floorPxArray,camera.plane.ceilingPxArray)
    
    camera.rayCastAll()
    projection = camera.plane.drawplane()
    screen.blit(projection, (0,0))

    clock = pygame.time.Clock()
    pygame.display.set_caption(str(clock.get_fps()))
    
    running = True
    pygame.key.set_repeat(1,50)

    while running:

        updateWalls = False
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False
                pygame.quit()

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_w:    # move forward
                if camera.castCollisionRay(clipDistance):
                    updateWalls = camera.walk(moveSpeed)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_s:    # move backwards
                if camera.castCollisionRay(-clipDistance):
                    updateWalls = camera.walk(-moveSpeed)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_a:    # turn left
                camera.rotate(-turnSpeed)
                updateWalls = True
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_d:    # turn right
                camera.rotate(turnSpeed)
                updateWalls = True

        if updateWalls:
            camera.rayCastAll()
            projection = camera.plane.drawplane()
            screen.blit(projection, (0,0))

        pygame.display.update()
        clock.tick(60)
        pygame.display.set_caption(str(clock.get_fps()))

# ==== main
profile.run('main()') # profiled run. For debugging only
#main()
