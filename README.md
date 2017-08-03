# Movie Recommendations with GRAKN.AI
-------------------------------------
To run this program, you will first need to have installed Grakn (this was written on 0.15.0). If you're coming here from the blog, then you probably already have grakn installed, but if you don't, you can use something like Homebrew to quickly get up and running, using the command
```
brew install grakn
```
You will then have to go into the Grakn directory and start the Grakn shell script, like so
```
/YOUR-GRAKN-DIRECTORY/bin/grakn.sh start
```
This will allow you to make queries through the Graql shell

## Running the program
You will need Python 2. for this project. I cannot guarantee compatibility with Python 3.

The `requirements.txt` has only 2 modules that need to be installed, so either you can run `pip install -r requirements.txt` from the Recommender directory, or you can just install NumPy and Pandas separately

Next you must go into `movieRecommender.py` and at the top of the file, replace the `PATH-TO-GRAKN` in
```
_GRAQL_PATH = "/PATH-TO-GRAKN/bin/graql.sh"
```
with the directory path and name that you used to start the Grakn engine itself. For example, on my machine this line looks like
```
_GRAQL_PATH = "/Users/nickpowell/Documents/Grakn/bin/graql.sh"
```
-------------------------------------
If it is your first time running the program, you will need to run it with the `buildGraph` flag on in order to build the ontology and ruleset. You will also need to specify a Graql keyspace with `-k`, and a directory to use with `-d` (the 2 options are `small` and `large`, for the small and large versions of the dataset). The shell command looks like this:
```
python ./movieRecommender.py -k insert_your_keyspace_here -d small --buildGraph
```
If you have multiple versions of Python installed, you may want to specify the 2. version, for example
```
python2.7 ./movieRecommender.py -k insert_your_keyspace_here -d small --buildGraph
```
Once you have loaded the ontology and ruleset for a particular keyspace, REMOVE the `--buildGraph` flag from your command and on every subsequent program execution to that keyspace, simply use
```
python ./movieRecommender.py -k insert_your_keyspace_here -d small
```
If you try to add the ontology to a keyspace that already has the ontology loaded, you may encounter errors, especially if you have made changes to the ontology.gql file.
