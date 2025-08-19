import requests
import graphviz

class Course: #Contains all the functions needed :)
    API = "https://sis.jhu.edu/api/classes/"
    KEY = ""
    KEYSTR = "?key="+KEY

    def __init__(self,r):
        #Stuff created on .create()
        course_dict = r.json()[-1]
        self.raw = course_dict
        self.name = course_dict["Title"]
        self.courseid = course_dict["OfferingName"]
        self.coursecode = "".join(self.courseid[:10].split("."))
        self.term = course_dict["Term"]
        self.returncode = r.status_code
        #stuff created on .get section data
        self.description = None #Can be None(not INIT) or some string or -1 if get section data fails
        self.sectionData = None #Can be None(not INIT) or some the dict of section data or -1 if get section data fails
        self.gotSection = False
        self.prereqs = {} #An object dict, can be -1 if get section data fails, empty if none loaded
        self.gotAllPrereqs = False
        #useful 'tree' data
        self.courselist = {}
        self.parents = {}
        self.root = None
        self.alternatives = {}

    @staticmethod
    def setkey(key):
        Course.KEY = key
        Course.KEYSTR = "?key="+key;

    def getSectionData(self):
        """
        A Change-in-place function!
        loads in the section data and fills in the fields that directly require it. (Prereqs wont be filled)
        
        Returns:
        0, worked fine
        -1, worked bad
        """
        if self.gotSection == False: #If the section data has not been loaded yet
            print(f"Getting section data for {self.courseid}...")
            section = self.raw["SectionName"]
            #Get the class + section data
            r = requests.get(Course.API + self.coursecode + section + Course.KEYSTR)

            #ERROR CHECKING
            if r.status_code != 200:
                
                #Attempted error correction:
                #Sometimes, the course will return without section data but wont return with section data
                #In this case, loop through possible section codes
                #A list of section numbers to attempt
                sectionsToAttempt = set() #This is being INIT here so that it can be accessed by the else:

                if r.status_code == 500:
                    print(f"ERROR: {r.status_code}, FOR CLASS: {self.courseid}, SECTION: {section}")
                    #THIS IS (SHOULD BE) THE ONLY CASE WHERE A DUPE REQUEST IS DONE 
                    #TODO: Try to find an intelligent solution to this without having to add the json into the class
                        #because adding the json would just add so much data into each object (So much data)
                        #Is adding all that data a problem? Idk Maybe not try both out
                    rNosection = requests.get(Course.API + self.coursecode + Course.KEYSTR) 
                    rjNosection = rNosection.json()

                    #The purpose of this is to loop through the section numbers, try to query for that section
                    #sectionsToAttempt = set() #Already INIT above the if
                    for i in range(len(rjNosection)): #Get all the sections to attempt
                        sectionsToAttempt.add(rjNosection[i]["SectionName"])
                    sectionsToAttempt.remove(section)                        

                    #Loop through the sections and
                    for section in sorted(list(sectionsToAttempt)): #Small to end so that it checks the most recent first

                        print(f"Trying section {section}...")
                        #Get the request
                        r = requests.get(Course.API + self.coursecode + section + Course.KEYSTR)
                        if r.status_code == 200: #SUCCESS WE GOT DATA!!!
                            print("SUCCESS: Data found!")
                            term = r.json()[-1]["Term"]
                            print(f"WARNING: the data from this course may not be up to date. It is from term: {term}")
                            break
                        else: #Didn't get data
                            continue
                    else:
                        
                        self.sectionData = -1
                        self.description = -1
                        self.gotSection = True
                        print(f"Can't find any section data for: {self.courseid}")
                        return -1
                        #raise Exception(f"Can't find any section data for: {self.courseid}")

                else:
                    raise ValueError(f"ERROR: {r.status_code} FOR CLASS: {self.courseid} SECTION: {section}")

            rj = r.json() #get the json (The actual data)

            #Check for errors
            if rj == []: 
                raise ValueError(f"Can't find json when querying section {section} for {self.courseid}")
            #END ERROR CHECKING

            sectionDetails = rj[-1]["SectionDetails"][0]

            #(Im very curious if this is possible because for some reason section details is put in a list)
            if len(rj[-1]["SectionDetails"]) > 1:
                raise ValueError(f"Section Details are long. Len {len(sectionDetails)} Course {self.courseid} section {section}")

            self.sectionData = sectionDetails
            self.description = sectionDetails["Description"]
            self.term = rj[-1]["Term"]
            self.gotSection = True #Set got section data to true
            return 0

        else: #If the section data has been loaded already
            raise ValueError(f"This object {self.courseid} already has section data")
        
    def getPrereqs(self,taken = []):
        """
        A Change-in-place function!
        loads in the section data and then get the prereqs and change them into objects

        And Return function 
        Returns the entire list of the prereqs all in one list (including alternatives)
        Should only return the objects, not the exceptions/Errors (Like EN990100)
        Also returns if the prereqs that were retrieved have already been loaded in prior to this (i.e. a dupe)
        So, returns a list which tells which index of the return is a dupe if it is false its not a dupe
        """
        #Init return list
        prereqList = []
        dupeBoolList = []

        if self.gotSection == False: self.getSectionData()
        if self.sectionData == -1:
            self.prereqs = -1
            self.gotAllPrereqs = True
            print(f"ERROR: Can't get prereqs for {self.courseid}")
            #Return empty list because there are no prereqs to return (don't return any object because it will get into the extend)
            #We return true here because there is no point to continue looking at prereqs bc of this one
            #False when being returned just means we continue looking
            return ([True],[]) 
        else:
            print(f"Getting prereqs for {self.courseid}...")
            #Get the prereqs expression as a str
            prereqsRaw = self.sectionData["Prerequisites"]
            
            #Get prereq expressions
            reqCodes = []
            for req in prereqsRaw:
                reqexpr = req["Expression"] #Get the expression
                print(f"Got: {reqexpr}")
                #Remove unnessesary parts
                reqexpr = reqexpr.replace("(^","")
                reqexpr = reqexpr.replace("^)","")

                #Split by and (Ensuring that they turn into different lists)
                for courseAndEq in reqexpr.split("^AND^"):
                    #Split by OR
                    courses = courseAndEq.split("^OR^")
                    
                    #Change them into their forms without periods
                    courses = ["".join(elm[:10].split(".")) for elm in courses]
                    print(f"Gave: {courses}")
                    reqCodes.append(courses)
            
            #Change prereqs into their objects
            for req in reqCodes:
                try:
                    #If any course in taken matches a course in the req 
                    # (Because all the courses in a single req are alts)
                    # then skip creating the object
                    for takencourse in taken:
                        if takencourse in req:
                            raise Exception(f"Not an error. Course {takencourse} already taken (in {req})")
                        
                    #Create the first (main) course
                    course1bool, course1 = Course.create(req[0],self)
                    prereqList.append(course1)
                    dupeBoolList.append(course1bool)

                    #Loop through the rest of the alternative courses
                    #(Only runs if there are more than one in the list)
                    altCourses = {}
                    for i in range(1,len(req)):
                        coursebool, course = Course.create(req[i],self)
                        prereqList.append(course)
                        dupeBoolList.append(coursebool)
                        altCourses[course.coursecode] = course

                    #load the altcourses into the alternatives
                    #only reason its doing this is to test for the situation when two parents have diff alternatives
                    if altCourses != {}: course1.alternatives[self.coursecode] = altCourses
                    #Load the prereqs into
                    self.prereqs[course1.coursecode] = course1

                except Exception as e:
                    print(e)
                    self.prereqs[req[0]] = req[0]

            #All prereqs have been got, we are done!
            self.gotAllPrereqs = True
            return dupeBoolList, prereqList

    def printPrereqs(self):
        """
        Print output function, no return value
        Prints out the immediate prereqs of a single course. Includes the alternatives prepended by OR
        """
        print(f"Pre-reqs of: {self.name}, {self.courseid}")
        
        #Self.prereqs has 4 cases, 
        # not loaded (So got all is false),
        # -1 (from section data errors)
        # empty (no prereqs), 
        # full of objs, 
        if self.gotAllPrereqs == False:
            #raise an error because this should never happen
            raise Exception(f"Pre-reqs not loaded yet for {self.courseid}")

        elif self.prereqs == -1:
            #just print because I don't care if this happens, just want to know
            print(f"ERROR: Can't print pre-reqs for {self.courseid}, they loaded with an error")

        elif self.prereqs == {}:
            #Print because this simply should print like this
            print(f"No pre-reqs")

        else:
            for req in self.prereqs.values():

                #Match for the type of the req
                match req:
                    case Course():
                        print(f" - {req.courseid}, {req.name}")

                        #if there are alternatives under this parent
                        if self.coursecode in req.alternatives.keys():
                            #Print all the alts
                            for alt in req.alternatives[self.coursecode].values():
                                print(f" OR {alt.courseid}, {alt.name}")

                    #This can happen if the course cant be found
                    case str():
                        print(f" - {req}")

                    #Blanket else case
                    case _:
                        raise ValueError(f"ERROR: Unexepected type ({type(req)}) found as ({req})")

    def printParents(self):
        """
        Print output function, no return value
        Prints out the immediate parents of a single course. Includes if it's an alternative
        """
        print(f"Under {self.root.name}, {self.name} is a prereq for:")
        for course in self.parents:
            print(f" - {course.courseid}, {course.name} ",end = "")
            #handle if it is an alternative
            if self.coursecode not in course.prereqs: #this means it's an alternative or there is an error
                for req in course.prereqs:
                    if not req.alternatives and self.coursecode in req.alternatives[course.coursecode]:
                        print(f"(As an alternative to {req.name})")
            
            #handle if it has alternatives
            if not self.alternatives and not self.alternatives[course.coursecode]:
                print("(With alternatives, ",end="")
                for alt in self.alternatives[course.coursecode].values():
                    print(alt.name,end=" ")
                print()

    def printGraphvizTree(self,dot = None,view = True):
        """
        Visual output function
        outputs a (pdf?) of the tree of prereqs under a course

        """
        if dot == None: dot = graphviz.Digraph()
        dot.node_attr = {"shape":"box"}
        dot.edge_attr = {"dir":"back"}
        if self.root != self:
            raise Exception("Please call printGraphvizTree with the root node")

        dot = self.createnodes(dot)
        dot = Course.createedges(dot,{self.coursecode+"_":self})
        
        dot.render("graph",view = view)
        return dot
            
    def createnodes(self,dot):
        
        if self.root != self:
            raise Exception("Please call printGraphvizTree with the root node")

        for course in self.courselist.values():
            if not course.parents.values():
                dot.node(course.coursecode + "_",course.name)
            else:
                for parent in course.parents.values():
                    dot.node(course.coursecode + "_" + parent.coursecode,course.name)

        return dot

    @staticmethod
    def createedges(dot,courses,loaded = []):
        print(f"_____________________________next layer_____________________________")
        #INIT
        nextlayercourses = {}
        #Each course to look through
        for nodecode,course in courses.items():
            #Each prereq in the course
            #    raise ValueError()
            if type(course.prereqs) != int:
                for req in course.prereqs.values():
                    match req:
                        case Course():
                            reqnodecode = req.coursecode+"_"+course.coursecode
                            #Check if it has already been connected to something else
                            if reqnodecode in loaded:
                                #Do nothing
                                print(f"{reqnodecode} already loaded")
                            else: 
                                print(f"{reqnodecode} loading...")
                                #make the edge
                                dot.edge(nodecode,reqnodecode)
                                #add to the loaded list and next layer of courses
                                loaded += [reqnodecode]
                                nextlayercourses[reqnodecode] = req

                            #Handle alternatives
                            if  bool(req.alternatives.get(course.coursecode,False)):
                                #Same ranks list
                                sameranks = [reqnodecode]
                                #Look through the alternatives
                                previous = req
                                for alt in req.alternatives[course.coursecode].values():
                                    #Alt codes
                                    altnodecode = alt.coursecode+"_"+course.coursecode
                                    previousnodecode = previous.coursecode+"_"+course.coursecode
                                    if altnodecode in loaded:
                                        #Do nothing
                                        print(f"{altnodecode} already loaded")
                                    else: 
                                        print(f"{altnodecode} loading...")

                                        #make the edge
                                        dot.edge(previousnodecode,altnodecode,arrowtail = "none",label = "OR")
                                        
                                        #add to the loaded list and next layer of courses
                                        loaded += [altnodecode]
                                        nextlayercourses[altnodecode] = alt
                                        previous = alt
                                        sameranks += [altnodecode]

                                #do the same ranks
                                rankstr = "{rank = same"
                                for string in sameranks:
                                    rankstr += (";"+string)
                                else:
                                    rankstr += "}\n"
                                    dot.body += [rankstr]



                        case str():
                            if req in loaded:
                                print(f"{req} already loaded")
                            else:
                                print(f"{req} loading...")
                                dot.edge(nodecode,req)
                                loaded += [req]

                        case _:
                            raise Exception(f"ERROR: Unexpected type ({type(req)}), for ({req})")
        if bool(nextlayercourses): dot = Course.createedges(dot,nextlayercourses,loaded=loaded)
        return dot

    @staticmethod
    def recursiveGetPrereqs(root,depth,courses,taken = []): #TODO: ADD TAKEN FUNCTIONALITY
        """
        A Change-in-place function!
        Goes layer by layer and grabs all of the classes
        """
        if depth > 0:
            thisLayerCourseList = [] #The list of the next layer's courses
            dupeBoolList = [] #The bool list of if the next layer's courses have already been loaded in
            for course in courses:
                dupeBool, reqList = course.getPrereqs(taken = taken) #append the list of this course's prereqs
                thisLayerCourseList.extend(reqList)
                dupeBoolList.extend(dupeBool)
            #Check if all these classes have already been loaded in
            if False not in dupeBoolList:
                print("All courses already found!")
                print("Done getting tree!")
            else:
                #If a course has already been loaded in there is no reason to load it in again
                uniqueCourses = []
                for i,course in enumerate(thisLayerCourseList):
                    #When a bool is true, it hasn't been loaded yet
                    if dupeBoolList[i] == False:
                        uniqueCourses.append(course)

                Course.recursiveGetPrereqs(root,depth-1,uniqueCourses)
        else:
            print("Done getting tree!")
    
    @staticmethod
    def create(coursecode,parent):
        """
        A Return function!
        
        requests and returns the course as an object with basic data loaded in from the SIS api
        Basic data being the data given without section data
        Also, adds the course into the parent(s)'s prereqs
        Also, returns a bool indicating if the returned course is dupe or not (Has been loaded in or not)
        The return structure is a tuple:
        (bool, course)
        """
        #Print out some info so they know whats happening
        print(f"Getting {coursecode}...")
        #If the data has already been grabbed, give this
        if type(parent) == Course and coursecode in parent.root.courselist.keys():
            course = parent.root.courselist[coursecode]
            #Add this new parent to the 
            course.parents[parent.coursecode] = parent
#Not sure we want prereq assignment here
#for courseParent in course.parents.values():
#courseParent.prereqs[course.coursecode] = course

            return True, course #RETURNS THE COURSE OBJECT (CHECK IF ITS A DUPE IN OTHER PLACES)

        r = requests.get(Course.API + coursecode + Course.KEYSTR) #Get the course (Without section data)
        #Check for errors
        if r.status_code != 200: 
            raise ValueError(f"STATUS CODE {r.status_code} FOR CLASS: {coursecode}")
        
        rj = r.json() #get the json (The actual data)
        #Check for errors
        if rj == []: 
            raise ValueError(f"CANT FIND CLASS: {coursecode}")
        
        else:
            #Create a course object
            course = Course(r)
            match (parent):
                case Course():
                    course.parents[parent.coursecode] = parent
                    course.root = parent.root
                    course.root.courselist[course.coursecode] = course
                    
#Not sure we want prereq assignment here
#parent.prereqs[course.coursecode] = course

                case None:
                    course.root = course
                    course.root.courselist[course.coursecode] = course

                case _:
                    raise ValueError("ERROR: WRONG TYPE",parent)

            return False, course

def getClassCode(): #Currently the only one not inside the object
    print("Input a class code: (e.g. 'AS.110.202')")
    totalCode = input().upper()
    code = "".join(totalCode.split("."))

    return code

if __name__ == "__main__":
    infile = open("key.txt","r")
    key = infile.read()
    Course.setkey(key)
    coursecode = 'EN520445' #getClassCode()
    course1 = Course.create(coursecode,None)[1]
    #course2 = Course.create("EN520219",None)[1]
    course1.recursiveGetPrereqs(course1, 100,[course1])
    #course2.recursiveGetPrereqs(course2,100,[course2])
    course1.printGraphvizTree(view = True)
    #course2.printGraphvizTree(view = True)
    print("Finished")