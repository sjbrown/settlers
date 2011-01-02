def longestRoadLength(player):
    # a player's road network can be thought of as a 
    # (possibly disconnected) graph that can have cycles

    def visitRoad(road):
        edge = road.location
        if not edge:
            # player hasn't placed this road on the board yet
            return 0
        lCorner = edge.corners[0]
        rCorner = edge.corners[1]
        #visitedCorners = [lCorner]
        visitedEdges = [edge]
        lLen = 1 + max([walkLen(lCorner, e, #visitedCorners,
                                visitedEdges)
                        for e in lCorner.edges])
        #visitedCorners = [rCorner]
        visitedEdges = [edge]
        rLen = 1 + max([walkLen(rCorner, e, #visitedCorners,
                                visitedEdges)
                        for e in rCorner.edges])
        return max([lLen, rLen])

    def walkLen(fromCorner, edge, #visitedCorners, 
                visitedEdges):
        if edge == None:
            # corners have 3 edges, but water-adjacent corners can have
            # one of the corners == None
            return 0
        if not edge.road:
            return 0
        if edge.road.owner != player:
            return 0
        if edge in visitedEdges:
            return 0
        toCorner = edge.otherCorner(fromCorner)
        #if toCorner in visitedCorners:
            #return 1

        #visitedCorners = visitedCorners[:]
        #visitedCorners.append(toCorner)
        visitedEdges = visitedEdges[:]
        visitedEdges.append(edge)

        return 1 + max([walkLen(toCorner, e, #visitedCorners, 
                                visitedEdges)
                        for e in toCorner.edges])

    if not player.roads:
        return 0
    return max([visitRoad(r) for r in player.roads])
            
