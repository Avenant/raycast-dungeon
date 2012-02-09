# Wolfenstein 3-D style ray caster [ COMPILED EXTENSION MODULES ]
# By Jozef Kolarovic, 2011
# Ray casting logic carried out here to boost speed :)


import math
from libc.stdlib cimport malloc,free

# [ Module-level variables ]
cdef:
	# "Constants" 
	int width,height,fov, mapSizeX, mapSizeY
	float dirAngle, rayIncrement, distToPlane
	float sinTable[3600], cosTable[3600], tanTable[3600]
	float *floorDistances
	int **floorTex
	int **ceilTex
	int **walls
	
	# return arrays
	int **floorCeilingArray
	

	# Per-cast variables  
	float xpos, ypos

	
# return arrays
#floorCeilingArray = []
#cdef int *wallHeights
wallHeights = []
wallTextures = []
wallTexOffsets = []

# "constructor" :)
def init(int w, int h, int FOV, wallArray ,floorCeilDistances):
	
	global height, width, fov, walls, floorDistances, floorCeilingArray, rayIncrement, distToPlane, sinTable, cosTable, tanTable, mapSizeX, mapSizeY
	
	width = w
	height = h
	fov = FOV


	# create wall arrays
	mapSizeX = len(wallArray)
	mapSizeY = len(wallArray[0])
	
	walls = <int**>malloc(mapSizeX * sizeof(int*))
	for i in xrange(mapSizeX):
		walls[i] = <int*>malloc(mapSizeY * sizeof(int))
	
	# populate wall arrays
	for i in xrange(mapSizeX):
		for j in xrange(mapSizeY):
			walls[i][j] = <int>wallArray[i][j]
			
	floorDistances = <float*>malloc(height * sizeof(float))
	for i in xrange(height):
		floorDistances[i] = <float>floorCeilDistances[i]
	
	
	# create floor/ceiling return array
	floorCeilingArray = <int**>malloc(width * sizeof(int*))
	for i in xrange(width):
		floorCeilingArray[i] = <int*>malloc(height * sizeof(int))

	
	# precompute trig. values
	cdef float angle = 0.0
	for i in xrange(3600):
		rad = math.radians(angle) + 0.0001
		sinTable[i] = math.sin(rad)
		cosTable[i] = math.cos(rad)
		tanTable[i] = math.tan(rad)
		angle += 0.1
	
	rayIncrement = float(fov) / float(width)
	distToPlane = (width / 2) / tanTable[(fov / 2) * 10]
	
	#wallHeights = <int*>malloc(width)

	
	# populate return arrays
	for i in xrange(width):
		wallHeights.append(0)
		#wallHeights[i] = 0
		wallTexOffsets.append(0)
		wallTextures.append(0)
	
	


def setFloorCeilTextures(floorTexArray,ceilTexArray):
	global floorTex, ceilTex
	
	size = len(floorTexArray[0])
	
	# allocate array memory
	floorTex = <int**>malloc(size * sizeof(int*))
	ceilTex = <int**>malloc(size * sizeof(int*))
	for s in xrange(size):
		floorTex[s] = <int*>malloc(size * sizeof(int))
		ceilTex[s] = <int*>malloc(size * sizeof(int))
	
	# populate arrays
	for x in xrange(size):
		for y in xrange(size):
			floorTex[x][y] = <int>floorTexArray[x][y]
			ceilTex[x][y] = <int>ceilTexArray[x][y]
	

	
def raycastAll(float xp, float yp, float angle):
	
	global wallHeights, wallTexOffsets, dirAngle, xpos, ypos, floorCeilingArray
	
	xpos = xp
	ypos = yp
	
	dirAngle = angle
	degrees = dirAngle - (fov / 2)
	currentAngle = degrees % 360
	
	cdef:
		# for floor casting...
		int floorStart, numPixels
		int texX,texY
		int wallX, wallY
		float weight, walldist
		int x,y
		
	for x in xrange(width):
		results = castWallRay(currentAngle)
		wallX = <int>results[0][0]
		wallY = <int>results[0][1]
		
		walldist = <int>results[1]
		
		wallHeights[x] = <int>round(64 / walldist * distToPlane)
		#wallTextures[x] = ...... fillmein .......
		wallTexOffsets[x] = results[2]
		
		# cast floors --------------------
		floorStart = (height / 2) + (wallHeights[x] / 2)
		numPixels = height - floorStart
		
		for y in xrange(numPixels):
			weight = floorDistances[floorStart + y] / walldist
			
			texX = <int>(weight * wallX + (1 - weight) * xpos) % 64
			texY = <int>(weight * wallY + (1 - weight) * ypos) % 64
			
			floorCeilingArray[x][floorStart + y] = floorTex[texX][texY]
			floorCeilingArray[x][floorStart - wallHeights[x] - y] = ceilTex[texX][texY]

		# increment angle ----------------
		currentAngle += rayIncrement	
		if (currentAngle > 360):
			currentAngle = currentAngle % 360

		
	return (wallHeights,wallTexOffsets)
	
	

#casts a single ray for wall raycasting
cdef castWallRay(angle):
	
	cdef:
		int x,y
	
	angle *= 10
	angle = abs(int(angle))		#  angle *10 for lookup table allows for higher degree of accuracy
	
	xdelta = sinTable[angle]
	ydelta = cosTable[angle]
	beta = cosTable[abs(int(dirAngle * 10) - angle)] # for correcting fishbowl
	
	distances = []
	H = [0,0]   # horizontal intersection
	V = [0,0]   # vertical intersection
	ds = 1      # used to flip distance calc. 
	Ya = 0      # Y grid increment 
	Xa = 0      # X grid increment

	# ----- Horizontal intersections ------------------------------
	# 1. finding the coordinate of A.
	if ydelta < 0:              # ray facing up
		H[1] = int(ypos / 64) * (64) - 0.0001
		Ya = -64
		ds = -1
	else:                       # ray facing down
		H[1] = int(ypos / 64) * (64) + 64
		Ya = 64
		ds = 1
		
	# get matching X value
	H[0] = xpos + (H[1] - ypos) * tanTable[angle]
	Xa = Ya * tanTable[angle]

	horizontalWallSearch = True
	while horizontalWallSearch:
		x = int(H[0] / 64)
		y = int(H[1] / 64)

		if (x >= 0 and x < mapSizeX) and (y >= 0 and y < mapSizeY):
			if walls[x][y] != 0: # found... calc. distance
				ydist = abs(ypos - H[1])
				distances.append((ydist * ds) / cosTable[angle]) # could also use pythagoras here (slower)
				horizontalWallSearch = False
			else:                       # next intersection!
				H[0] += Xa
				H[1] += Ya
		else:              # no wall reached 
			distances.append(999999)
			horizontalWallSearch = False

	# ----- Vertical intersections ------------------------------
	if xdelta < 0:              # ray facing left
		V[0] = int(xpos / 64) * (64) - 0.0001
		Xa = -64
		ds = -1
	else:                       # ray facing right
		V[0] = int(xpos / 64) * (64) + 64
		Xa = 64
		ds = 1

	# get matching Y value
	V[1] = ypos + ((V[0] - xpos) / tanTable[angle])
	Ya = Xa / tanTable[angle]
	
	# check for wall...
	verticalWallSearch = True
	while verticalWallSearch:
		x = int(V[0] / 64)
		y = int(V[1] / 64)

		
		if (x >= 0 and x < mapSizeX) and (y >= 0 and y < mapSizeY):
			if walls[x][y] != 0: # found... calc. distance
				xdist = abs(xpos - V[0])
				distances.append((xdist * ds) / sinTable[angle])
				verticalWallSearch = False
			else:                       # next intersection!
				V[0] += Xa
				V[1] += Ya
		else:              # no wall reached
			distances.append(999999)
			verticalWallSearch = False

	# use the lowest distance between x and y, set texture offset
	distance = min(distances)
	if distances[0] == distance:
		textureColumn = H[0] % 64
		wallpoint = (H[0],H[1])
	else:
		textureColumn = V[1] % 64
		wallpoint = (V[0],V[1])
		
	distance *= beta            # correct fishbowl
	return (wallpoint,distance,textureColumn)
	
	
# convert int** to python list and return
def getFloorCeilArray(floorCeilArray):
	
	for w in xrange(width):
		for h in xrange(height):
			floorCeilArray[w][h] = floorCeilingArray[w][h]
			
	return floorCeilArray
	
#def getWallheights():
#	return wallHeights
	
def getWallTexOffsets():
	return wallTexOffsets
	
#def getWalls():
#	return walls
	
def getHeight():
	return height
