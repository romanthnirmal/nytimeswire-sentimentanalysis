# To add a new cell, type '# %%'
# To add a new markdown cell, type '# %% [markdown]'
# %% [markdown]
# ## Get API Key by creating The NewYork Times Developer account
# https://developer.nytimes.com/accounts/createhttps://developer.nytimes.com/accounts/create
# %% [markdown]
# ## Get Google Cloud Credentials - assuming you have Google cloud access
# 
# https://cloud.google.com/docs/authentication/getting-started

# %%
#!pip3 install webdrivermanager
#!webdrivermanager firefox chrome --linkpath /usr/local/bin


# %%
# Library imports and config
import os
import pandas as pd
import urllib3, requests
from google.cloud import language_v1
from google.cloud.language_v1 import enums
from tqdm import tqdm
from bokeh.io import output_notebook, show

from bokeh.models import (ColumnDataSource, HoverTool, LabelSet)
from bokeh.plotting import figure, output_file
from bokeh.palettes import Set3
#from bokeh.io import export_png

output_notebook()

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.max_colwidth', 0)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# %%
# Google cloud credentials goes here if you don't already have declared
os.environ['GOOGLE_APPLICATION_CREDENTIALS']='gcp-creds.json'

# The New York Times API Key goes here
API_KEY="GenerateOneFrom-NYT"


# %%
# Function to get latest articles from NewYork Times Wire API and store it as Data Frame
def get_nyt_articles(API_KEY,limit=500):
    url = "https://api.nytimes.com/svc/news/v3/content/all/all.json?api-key="+API_KEY+"&limit="+str(limit)
    try:
        page = requests.get(url, verify=False)
        df_page=pd.json_normalize(page.json()['results'])[['slug_name','byline','section','item_type','material_type_facet','des_facet','org_facet','per_facet','geo_facet','title','abstract','first_published_date']]
        df_page['first_published_date_parsed']=pd.to_datetime(df_page['first_published_date'],format='%Y-%m-%d %H:%M:%S').dt.tz_convert('Europe/London')
    except:
        print("Error generating articles from The New York Times")
        return
    return df_page


# %%
# Function to initialize GCP Natural Langugage Service client
def get_client(text_content):
    client = language_v1.LanguageServiceClient()
    type_ = enums.Document.Type.PLAIN_TEXT
    language = "en"
    document = {"content": text_content, "type": type_, "language": language}
    encoding_type = enums.EncodingType.UTF8
    return client, document, encoding_type


# %%
# Function to invoke google cloud analyze sentiment API
def analyze_sentiment(text_content,articleid):
    try:
        client, document, encoding_type = get_client(text_content)
        response = client.analyze_sentiment(document, encoding_type=encoding_type)
        results=[]
        document={}
        document['articleid']=articleid
        document['level']='document'
        document['sentiment_score']=float(response.document_sentiment.score)
        document['sentiment_magnitude']=float(response.document_sentiment.magnitude)
        document['language']=str(response.language)
        results.append(document)
        for sentence in response.sentences:
            allsen={}
            allsen['articleid']=articleid
            allsen['level']='sentence'
            allsen['sentence_text']=str(sentence.text.content)
            allsen['sentiment_magnitude']=float(sentence.sentiment.magnitude)
            allsen['sentiment_score']=float(sentence.sentiment.score)
            results.append(allsen)
    except:
        print("Error generating sentiment analysis using Google cloud")
    return results


# %%
# Function to iterate through New York times articles and call API and append results to a dataframe
def gcp_analyze_sentiment(df):
    dfBase=pd.json_normalize(analyze_sentiment('Test','Doc1'))
    for index,row in tqdm(df.iterrows()):
        try:
            results1=analyze_sentiment(str(row['title'])+". "+str(row['abstract']),row['slug_name'])
            df1=pd.json_normalize(results1)
            dfBase=pd.concat([dfBase,df1])
        except:
            print("Error analysing: {}".format(row['slug_name']))
    return dfBase


# %%
def get_top10(dfOut,colname,ascending=False):
    if not ascending:
        # Prepare chart data - top 10 highest ranking sentiment score by individual setnences against articleid
        dfX1=dfOut[dfOut.sentence_text.isnull()].groupby([colname]).mean().nlargest(10,'sentiment_score')[['sentiment_score']].index.str[:40].tolist()
        dfY1=dfOut[dfOut.sentence_text.isnull()].groupby([colname]).mean().nlargest(10,'sentiment_score')[['sentiment_score']].values.round(2).tolist()
    elif ascending:
        # Prepare chart data - top 10 highest ranking sentiment score by individual setnences against articleid
        dfX1=dfOut[dfOut.sentence_text.isnull()].groupby([colname]).mean().nsmallest(10,'sentiment_score')[['sentiment_score']].index.str[:40].tolist()
        dfY1=dfOut[dfOut.sentence_text.isnull()].groupby([colname]).mean().nsmallest(10,'sentiment_score')[['sentiment_score']].values.round(2).tolist()

    dfY1=[y[0] for y in dfY1]
    return dfX1,dfY1


# %%
def generate_vis(dfX1,dfY1,xaxislabel):
    # Visualize

    sorted_score = sorted(dfX1, key=lambda x: dfY1[dfX1.index(x)])

    source = ColumnDataSource(data=dict(sentences=dfX1, sentiment_score=dfY1, color=Set3[10]))

    from math import pi

    p = figure(x_range=sorted_score, y_range=(-1,1),height=800, width=1000, title="The New York Times Wire - Sentiment Analysis", toolbar_location=None)
    p.vbar(x='sentences', top='sentiment_score', color='color', width=0.5,  source=source)

    hover_tool = HoverTool(tooltips=[("sentiment_score", "@sentiment_score")])

    labels = LabelSet(x='sentences', y='sentiment_score', text='sentiment_score',  source=source, render_mode='canvas')

    p.add_tools(hover_tool)

    p.xaxis.axis_label=xaxislabel
    p.yaxis.axis_label="Sentiment Score"
    p.xaxis.axis_label_text_font_size = "13pt"
    p.yaxis.axis_label_text_font_size = "13pt"
    p.xaxis.major_label_orientation = pi/3
    p.xaxis.major_label_text_font_size = "13pt"

    p.y_range.start = -1

    p.add_layout(labels)
    
    #export_png(p, filename=str(xaxislabel.strip())+".png")
    show(p)
    


# %%
# Execute article extraction from NYT
df_page=get_nyt_articles(API_KEY)

if df_page:
    # Execute the sentiment analysis across google cloud platform - sample 100
    dfBase0=gcp_analyze_sentiment(df_page.sample(10))

    # Join the score with original article extract
    dfOut=dfBase0.join(df_page.set_index('slug_name'), on='articleid')
else:
    # Read sample static file
    dfOut = pd.read_csv('dfOut.csv')


# %%
# Get highest positive ranking Organisation
(dfX1,dfY1) = get_top10(dfOut,'org_facet',False)
generate_vis(dfX1,dfY1,"Ranked Positive by Organisation")


# %%
# Get highest negative ranking Organisation
(dfX1,dfY1) = get_top10(dfOut,'org_facet',True)
generate_vis(dfX1,dfY1,"Ranked Negative by Organisation")


# %%
# Get highest positive ranking Geo location
(dfX1,dfY1) = get_top10(dfOut,'geo_facet',False)
generate_vis(dfX1,dfY1,"Ranked Positive by Geo Location")


# %%
# Get highest negative ranking Geo location
(dfX1,dfY1) = get_top10(dfOut,'geo_facet',True)
generate_vis(dfX1,dfY1,"Ranked Negative by Geo Location")


# %%
# Get highest positive ranking Geo location
(dfX1,dfY1) = get_top10(dfOut,'des_facet',False)
generate_vis(dfX1,dfY1,"Ranked Positive by Entities")


# %%
# Get highest negative ranking Geo location
(dfX1,dfY1) = get_top10(dfOut,'des_facet',True)
generate_vis(dfX1,dfY1,"Ranked Negative by Entities")


# %%
# Get highest negative ranking Geo location
(dfX1,dfY1) = get_top10(dfOut,'title',False)
generate_vis(dfX1,dfY1,"Ranked Positive by Text")


# %%
# Get highest negative ranking Geo location
(dfX1,dfY1) = get_top10(dfOut,'title',True)
generate_vis(dfX1,dfY1,"Ranked Negative by Text")


