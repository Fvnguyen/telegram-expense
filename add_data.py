import requests

url = "https://community-open-weather-map.p.rapidapi.com/weather"

def getweather(lat,lon):
    querystring = {"lon":lon,"lat":lat,"lang":"de","units":"metric"}
    headers = {
    'x-rapidapi-host': "community-open-weather-map.p.rapidapi.com",
    'x-rapidapi-key': "e8c26025abmsh045b21e5a969e8ap15fc5djsnbdc016803368"
    }
    response = requests.request("GET", url, headers=headers, params=querystring)
    wetter = eval(response.text)
    city =  wetter['name']
    temp = str(wetter['main']['temp'])
    summary = 'In '+city+' sind es gerade '+temp+'C°'
    return summary