# THis is an implementation plan for a new feature to interface with the met.no API. 

## Purpose
use the met.no api to get weather forecast data. the user should be able to extend the weather observatiopns from SILO with forecast data for downstream use in predictions. 

## use cases
The user should be able to download weather forecast data for a given location, supplied in lat lon coords.
The data  output should be summarised into a daily weather forecast. 
The user should be able to select the output format (SILO, APSIM, etc) and the data will be formatted in a dataframe to match data retrieved from the SILO-API. mapping between column names should be managed by the existing module `silo_variables.py` or similar central mapping.

a separate function should handle calling both silo-API and met.no API and m,merging the files so that silo data are used for observed data and met.no data are used for future forecast values. 


# plan
Review the API documentation here: https://api.met.no/weatherapi/locationforecast/2.0/documentation
you MUST access the openapi spec found within the documentation. 
