from argparse import ArgumentParser
from datetime import datetime
from subprocess import check_output
import csv
import numpy as np
import pandas as pd
import random
import re

_ANSI_COL_PATH = re.compile(b'\033\[[\d;]*m')

""" Insert local path to graql.sh below """
_GRAQL_PATH = "/PATH-TO-GRAKN/bin/graql.sh"

_ONTOLOGY_PATH = "movieOntology.gql"
_RULESET_PATH = "movieRules.gql"
_MOVIES_OUTPUT_PATH = "moviesinsert.gql"
_RATINGS_OUTPUT_PATH = "ratingsinsert.gql"

###########################################################################################
class MovieRecommender(object):

	###########################################################################################
	""" Initialization of the network """
	def __init__(self, params):
		self.keyspace = params[0]
		self.useLargeDb = params[1]
		self.buildGraph = params[2]
		self.batch_query_size = params[3]
		self.num_suggestions = params[4]
		self.fetch_limit = params[5]
		self.num_recommendations = params[6]
		self.movieDict = {}
		self.recsDict = {}
		self.queryResults = []
		self.genreDict = {
			'Action' 		: 0,
			'Adventure'		: 1,
			'Animation'		: 2,
			'Children'		: 3,
			'Comedy'		: 4,
			'Crime'			: 5,
			'Documentary'	: 6,
			'Drama'			: 7,
			'Fantasy'		: 8,
			'Film-Noir'		: 9,
			'Horror'		: 10,
			'IMAX'			: 11,
			'Musical'		: 12,
			'Mystery'		: 13,
			'Romance'		: 14,
			'Sci-Fi'		: 15,
			'Thriller'		: 16,
			'War'			: 17,
			'Western'		: 18
		}


	###########################################################################################
	""" Prefixes the given filename with the appropriate directory """
	def correctFilenamePrefix(self, filename):
		if self.useLargeDb:
			filename = 'data-large/' + filename
		else:
			filename = 'data-small/' + filename

		return filename


	###########################################################################################
	""" Creates instance variable dictionary of movies """
	def createMovieDict(self, filename):
		filename = self.correctFilenamePrefix(filename)
		
		with open(filename, 'rb') as movie_file:
			""" Start the reader """
			movie_reader = csv.reader(movie_file, delimiter=',')

			""" Skip the header line """
			movie_reader.next()

			for row in movie_reader:
				movie_id, title, year, genre_list = self.parseStringAndAssert(row)

				""" If the given row was properly formatted, this executes"""
				if not movie_id == "":
					self.movieDict[movie_id] = (title, year, genre_list)


	###########################################################################################
	""" Writes query to file and executes it batchwise. isRatingData == True if adding ratings, == False if adding movies """
	def executeBatch(self, query, isRatingData):
		path = ""
		if isRatingData:
			path = _RATINGS_OUTPUT_PATH 
		else:
			path = _MOVIES_OUTPUT_PATH

		f = open(path, 'w')
		f.write(query)
		f.close()
		check_output(_GRAQL_PATH + " -f " + path + " -k " + self.keyspace, shell=True)


	###########################################################################################
	""" Quick function to insert ontology and ruleset"""
	def insertOntology(self):
		check_output(_GRAQL_PATH + " -f " + _ONTOLOGY_PATH + " -k " + self.keyspace, shell=True)
		check_output(_GRAQL_PATH + " -f " + _RULESET_PATH + " -k " + self.keyspace, shell=True)


	###########################################################################################
	""" Insert movie data into the graph from one of the two directories """
	def insertMovieData(self):
		running_batch_count = 0
		query = ""
		""" Iterate through the movies in the dict and add them, batch-wise, to the graph """
		for movie in self.movieDict.keys():
			running_batch_count += 1			
			movie_tup = self.movieDict[movie]
			genres = movie_tup[2].split('|')

			movie_id = "\"" + movie + "\""
			movie_title = "\"" + movie_tup[0] + "\""
			release_year = movie_tup[1]
			insert_query = '''insert $x isa movie has movieId ''' + movie_id + ''' has title ''' + movie_title + ''' has releaseYear ''' + release_year 

			bitVector = 0
			for genre in genres:
				if genre in self.genreDict:
					newBit = 1 << self.genreDict[genre]
					bitVector ^= newBit

			insert_query += " has genreBitvec " + str(bitVector)  + "; "
			query += insert_query

			""" We can't run a batch query on all movies at once, because that causes memory problems. We choose the batch_size above """
			if running_batch_count >= self.batch_query_size:
				self.executeBatch(query, False)
				query = ""
				running_batch_count = 0

		self.executeBatch(query, False)


	###########################################################################################
	""" Insert users' rating data into the graph from one of the two directories """
	def insertRatingData(self, filename):
		filename = self.correctFilenamePrefix(filename)
		running_batch_count = 0

		users_query = ""
		relations_query = ""

		print("Inserting rating data...")

		with open(filename, 'rb') as ratings_file:
			ratings_reader = csv.reader(ratings_file, delimiter=',')

			""" Skip the header line """
			ratings_reader.next()
			user_list = []

			""" Get information about the first user in the csv file """
			first_user = ratings_reader.next()
			current_user_id = first_user[0]
			user_list.append(first_user)

			""" Iterate through all rows in the file """
			for line in ratings_reader:
				""" If we have reached a new user, we want to collect all the previous user's information """
				if line[0] != current_user_id:
					df = pd.DataFrame(user_list)
					df[2] = df[2].astype(np.float)

					ave_rating = df[2].mean()
					df[2] = np.where(df[2] >= ave_rating, 1, 0)

					""" Add the user to the graph """
					user_id = "\"" + current_user_id + "\""
					users_query += "insert $x isa user has userId " + user_id + " has aveRating " + str(ave_rating) + "; "

					""" Iterate through each row in the data frame, and add rating data to the query """
					for index, row in df.iterrows():	
						movie_id = "\"" + row[1] + "\""
						insert_query = " match $x isa movie has movieId " + movie_id + \
									"; $y isa user has userId " + user_id
						if row[2] == 1:
							insert_query += "; insert (liker: $y, liked: $x) isa did-like; "
						else:
							insert_query += "; insert (disliker: $y, disliked: $x) isa didnot-like; "

						relations_query += insert_query
						running_batch_count += 1

						""" If we have reached our batch size limit, we run the query """
						if running_batch_count >= self.batch_query_size:
							self.executeBatch(users_query, True)
							self.executeBatch(relations_query, True)
							users_query = relations_query = ""
							running_batch_count = 0

					user_list = []
					current_user_id = line[0]

				""" Regardless of the resolution of control flow above, we add the rating to the user list at the end"""
				user_list.append(line)


	###########################################################################################
	""" Deals with the format of the movies.csv file """
	def parseStringAndAssert(self, movie_row):
		movie_id = movie_row[0]
		genre_list = movie_row[len(movie_row)-1]
		title_and_year = movie_row[1]

		if len(movie_row) > 3:
			for i in range(2, len(movie_row)):
				title_year += movie_row[i]

		year_regex = re.compile('\(\d{4}\)')
		try:
			year_index = year_regex.search(title_and_year).start()
			title = title_and_year[0:year_index-1]
			year = title_and_year[year_index+1:year_index+5]

			""" We have to check EVERY movie for stray quotes"""
			start = 0			
			while title[start] == "\"":
				start += 1

			end = start + 1
			while (title[end] != "\""):
				if end == len(title) -1:
					end = len(title)
					break
				end += 1

			title = title[start:end]

			return (movie_id, title, year, genre_list)
		except:
			return ("", "", "", "")	

	###########################################################################################
	""" Helper function to fill in the object-scoped query result list that stores the results of each query I run as I run it """
	def addToDicts(self, liked, movieId):
		movie_query = "\"" + movieId + "\""
		if (liked):
			query = "match $x isa movie has movieId " + movie_query + "; $y isa movie has movieId $mid has genreBitvec $bvec; ($y, $x) isa recommendation; select $mid, $bvec; limit " + str(self.fetch_limit) + ";"
		else:
			query = "match $x isa movie has movieId " + movie_query + "; $y isa movie has movieId $mid has genreBitvec $bvec; ($y, $x) isa neg-recommendation; select $mid, $bvec; limit " + str(self.fetch_limit) + ";"

		query = "\'" + query + "\'"
		query_output = check_output(_GRAQL_PATH + " -e " + query + " -n -k " + self.keyspace, shell=True)
		result_string = re.sub(_ANSI_COL_PATH, '', query_output)
		result_string = result_string.split('\n')
		self.queryResults.append(result_string)


	###########################################################################################			
	""" Loops through the list of query results and calculates all the scores, genre-scaled """
	def calculateScores(self, genre_weights):
		for result_string in self.queryResults:
			""" Extract the movieId from the result string """
			for rec in result_string:
				rgx = re.compile('\d+')
				if rec:
					matches = [[m.start(), m.end()] for m in rgx.finditer(rec)]
					ix = rgx.search(rec).start()
					eix = rgx.search(rec).end()
					movieId = rec[matches[0][0]:matches[0][1]]
					bitVec = int(rec[matches[1][0]:matches[1][1]])

					bitfield = [1 if digit=='1' else 0 for digit in bin(bitVec)[2:]]
					genre_coef = 0
					for i in range(len(bitfield)):
						if bitfield[len(bitfield)-1-i] == 1:
							genre_coef += genre_weights[i]

					if movieId in self.recsDict:
						self.recsDict[movieId] += genre_coef
					else:
						self.recsDict[movieId] = genre_coef


	###########################################################################################
	""" Calculates the most recommended movies"""
	def getRecommendations(self, movies_liked, movies_disliked):

		""" First we create a vector of genre weights based on how often they appear in the arrays passed in """
		genre_weights = np.zeros((len(self.genreDict.keys()), 1))

		for liked in movies_liked:
			liked_tup = self.movieDict[liked]
			liked_genres = liked_tup[2].split('|')
			for genre in liked_genres:
				ix = self.genreDict[genre]
				genre_weights[ix] += 1

		for disliked in movies_disliked:
			disliked_tup = self.movieDict[disliked]
			disliked_genres = disliked_tup[2].split('|')
			for genre in disliked_genres:
				ix = self.genreDict[genre]
				genre_weights[ix] -= 1

		""" Convert it to its unit vector """
		genre_weights /= np.linalg.norm(genre_weights)

		""" Next, we query Grakn to find all recommended movies and add score from both user matches and genre matches to the score dict """
		self.calculateScores(genre_weights)
		self.calculateScores(genre_weights)

		rows = []
		for key in self.recsDict:
			rows.append([key, self.recsDict[key]])

		df = pd.DataFrame(rows, columns=['movieId', 'score'])
		df = df.sort_values('score', ascending=False)

		if len(df.index) > self.num_recommendations:
			return(df[0:self.num_recommendations])
		else:
			return(df[0:len(df.index)-1])


	###########################################################################################
	""" Returns the tuple of a random movie in the mapping"""
	def chooseRandomMovie(self):
		movie_id = random.choice(list(self.movieDict.keys()))
		return(movie_id, self.movieDict[movie_id])
		


###########################################################################################
""" Function to fetch all the program parameters """
def getProgramParameters():
	""" Initialize dict of all program parameters """
	program_parameters = {}

	program_parameters['num_suggestions'] 		= 15	# how many user responses are demanded and logged
	program_parameters['batch_query_size']		= 1000	# how large each batch that we insert into the graph is
	program_parameters['fetch_limit']			= 100   # how many max results are returne
	program_parameters['num_recommendations'] 	= 10    # how many movies are recommended by the program at the end

	return program_parameters


###########################################################################################
""" Ask the user for inputs and store results """
def getUserInputs(recommender):
	movies_liked = []
	movies_disliked = []
	print("\nYou will now receive movie suggestions, one after another. Type Y if you like the movie; type N if you do not; type ? if you do not know the movie and want to skip it. You must give " + str(recommender.num_suggestions) + " yes/no responses\n")

	""" Outputs suggestions for user input """
	for i in range(recommender.num_suggestions):

		(movie_id, randomMovie) = recommender.chooseRandomMovie()
		userInput = raw_input(randomMovie[0] + " (" + str(randomMovie[1]) + ") [y/n]: ")
		while userInput == '?':
			(movie_id, randomMovie) = recommender.chooseRandomMovie()
			userInput = raw_input("...trying again...\n" + randomMovie[0] + " (" + str(randomMovie[1]) + ") [y/n]: ")

		if userInput == 'y' or userInput == 'Y' or userInput == 'Yes' or userInput == 'yes':
			movies_liked.append(movie_id)
			recommender.addToDicts(1, movie_id)
		elif userInput == 'n' or userInput == 'N' or userInput == 'No' or userInput == 'no':
			movies_disliked.append(movie_id)
			recommender.addToDicts(0, movie_id)
		else:
			while not (userInput == 'y' or userInput == 'Y' or userInput == 'yes' or userInput == 'Yes' or userInput == 'n' \
				or userInput == 'N' or userInput == 'no' or userInput == 'No'):
				userInput = raw_input("Invalid input, please try again [y/n]: ")


	recs = recommender.getRecommendations(movies_liked, movies_disliked)
	print('---------------------------')
	print("Top 10 recommendations: ")

	for movieId in recs.iloc[:,0]:
		movie_info = recommender.movieDict[movieId]
		print(movie_info[0] + " (" + movie_info[1] + ")")
		

###########################################################################################
""" Parameters passed in are the keyspace and the bool 'buildGraph' which tells the program whether to build the ontology from scratch """
def main(keyspace, directory, buildGraph):

	program_parameters 	= getProgramParameters()
	num_suggestions 	= program_parameters['num_suggestions']
	batch_query_size	= program_parameters['batch_query_size']
	fetch_limit			= program_parameters['fetch_limit']
	num_recommendations = program_parameters['num_recommendations']

	useLargeDb =  True if (directory == 'large') else False

	params_list = []
	params_list.append(keyspace)
	params_list.append(useLargeDb)
	params_list.append(buildGraph)
	params_list.append(batch_query_size)
	params_list.append(num_suggestions)
	params_list.append(fetch_limit)
	params_list.append(num_recommendations)

	recommender = MovieRecommender(params_list)

	""" Create the movie dictionary """
	recommender.createMovieDict('movies.csv')

	""" Insert ontology and ruleset if buildGraph is True """
	if buildGraph:
		print("0/3...")
		recommender.insertOntology()
		print("1/3...ontology built")
		recommender.insertMovieData()
		print("2/3...movie data inserted")
		recommender.insertRatingData("ratings.csv")
		print("3/3...ratings data inserted")

	getUserInputs(recommender)


###########################################################################################
if __name__ == "__main__":
	parser = ArgumentParser(
		description="movieRecommender -k KEYSPACE -d DIRECTORY [--buildGraph]")
	parser.add_argument('-k', '--keyspace', help="The Graql keyspace to use", required=True)
	parser.add_argument('-d', '--directory', help="Which of the data directories to use (2 options)", choices= \
		['small', 'large'], required=True)
	parser.add_argument('--buildGraph', dest='buildGraph', help="Optional flag to build the ontology and ruleset if it has not already been built", action='store_true')
	parser.set_defaults(buildGraph = False)
	sysargs = parser.parse_args()
	main(sysargs.keyspace, sysargs.directory, sysargs.buildGraph)
