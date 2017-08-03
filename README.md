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
The `requirements.txt` has only 2 modules that need to be installed, so either you can run `pip install -r requirements.txt` from the Recommender directory, or you can just install NumPy and Pandas separately

In any case 
