import logging
from logging.handlers import RotatingFileHandler
import argparse
from flask import Flask, redirect, request, render_template, url_for, make_response, session, flash, send_file, render_template_string
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import requests.exceptions
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
from sklearn.tree import DecisionTreeRegressor
from plotly.subplots import make_subplots
import plotly.io as pio
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os, csv, json, collections
from flask_session import Session
import sqlite3
from flask_bcrypt import Bcrypt
import plotly.offline as pyo
import time
from googleapiclient.discovery import build
from datetime import datetime
from datetime import timedelta
import isodate
from pweoori import generate_top_artists_html, generate_top_tracks_html
# Define a list of possible date formats to try
date_formats = ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z"]

# Create a function to parse the date using multiple formats
def parse_date(date_str):
    for date_format in date_formats:
        try:
            return datetime.strptime(date_str, date_format)
        except ValueError:
            pass
    # If no format matches, return a default value (you can adjust as needed)
    return datetime(1900, 1, 1)

port = int(os.environ.get("PORT", 5000))

app = Flask(__name__)

# Configure logging
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] - %(message)s")
handler = RotatingFileHandler("app.log", maxBytes=10240, backupCount=10)  # Set log file size and backup count
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)  # Set the logging level (INFO, ERROR, DEBUG, etc.)

# Configure Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'  # You can choose other storage options
app.config['SESSION_PERMANENT'] = True
Session(app)

# Secret key for session security (change this to a long, random value)
app.secret_key = 'your_secret_key'

# Replace with actual values from your Spotify developer dashboard
client_id = 'ea26371962734711af4bdd86cc792590'
client_secret = 'a0c245cd868349c7b81bf06670eca480'
access_token_lifetime = 3600
api_key = 'AIzaSyDYurw5CRhf_Sm5auzAE0Rh1QMMUEVUXr4'

# Create the auth manager object with client ID, secret, redirect URI, and scopes
#https://tune.isthis.club/callback
auth_manager = SpotifyOAuth(client_id, client_secret, redirect_uri='http://127.0.0.1:5000/callback',
                            scope='user-library-read,user-top-read,user-read-recently-played,user-read-playback-state,user-modify-playback-state,user-read-currently-playing,playlist-read-private,playlist-modify-public,playlist-modify-private,user-follow-read,user-read-email,user-read-private',
                            cache_handler=None)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

def get_access_token(session, sp_oauth):
    refresh_token = session.get('refresh_token')
    access_token = session.get('access_token')
    access_token_expiration = session.get('access_token_expiration')
    
    if access_token and access_token_expiration and access_token_expiration > time.time():
        # The access token is valid, return it
        app.logger.info('Access Token is alive')
        return access_token
    
    if refresh_token:
        # The access token has expired or is missing, refresh it
        token_info = sp_oauth.refresh_access_token(refresh_token)
        if 'access_token' in token_info:
            access_token = token_info['access_token']
            access_token_expiration = time.time() + access_token_lifetime
            session['access_token'] = access_token
            session['access_token_expiration'] = access_token_expiration
            app.logger.info('Access Token was Renewed')
            return access_token
    
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/spotify')
def spotify():
    access_token = get_access_token(session, auth_manager)
    if access_token is not None:
        return redirect(url_for('dashboard'))
    auth_url = auth_manager.get_authorize_url()
    return render_template('index2.html', auth_url=auth_url)

@app.route('/youtube')
def youtube():
    file_content = session.get('uploaded_file')
    if file_content:
        return redirect('/process')
    return render_template('upload.html')

# Custom error handler for 404 errors
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(requests.exceptions.RequestException)
def request_error(error):
    app.logger.error(str(error))
    return render_template('error.html'), 500

@app.route('/callback')
def callback():
    try:
        # Retrieve the authorization code from the URL query parameters
        auth_code = request.args.get("code")

        # Use the authorization code to get an access token
        token = auth_manager.get_access_token(auth_code, as_dict=True, check_cache=False)

        # Store the access token and refresh token in the user's session
        access_token_expiration = time.time() + access_token_lifetime
        session['access_token'] = token["access_token"]
        session['access_token_expiration'] = access_token_expiration
        session['refresh_token'] = token["refresh_token"]

        return redirect(url_for("dashboard"))
    except Exception as e:
        # Handle the case where the authorization code is expired or there's an error
        return redirect(url_for("spotify"))

def get_user_basic_info(sp):
    # Use the Spotipy instance to retrieve the user's basic information
    user_info = sp.current_user()
    display_name = user_info['display_name']
    email = user_info['email']
    followers = user_info['followers']['total']
    country = user_info['country']
    profile_picture = user_info.get('images', [{}])[0].get('url') if user_info.get('images') else None

    # Return the user's basic information as a dictionary
    return {'display_name': display_name, 'email': email, 'followers': followers, 'country': country, 'profile_picture': profile_picture}

@app.route('/dashboard')
def dashboard():
    access_token = get_access_token(session, auth_manager)
    if access_token is None:
        return "token is missing. Please authenticate with Spotify."

    # Create Spotipy object with the authenticated access token
    sp = spotipy.Spotify(auth=access_token, requests_timeout=40)
    
    user_info = get_user_basic_info(sp)
    display_name = user_info['display_name']
    email = user_info['email']
    followers = user_info['followers']
    country = user_info['country']
    profile_picture = user_info['profile_picture']

    # Render the HTML template and pass in the user's basic information
    return render_template('su.html', display_name=display_name, email=email, followers=followers, country=country, user_profile_picture=profile_picture)


def process_uploaded_file(file_content):
    data = json.loads(file_content)

    pruned = {}
    total_watches = 0
    top_channels = collections.Counter()

    for entry in data:
        if (
            entry["header"] == "YouTube Music"
            and entry["title"] != "Visited YouTube Music"
            and "https://www.youtube.com/watch?v=" not in entry["title"]
            and entry["title"] != "Watched a video that has been removed"
        ):
            title = entry["title"][8:]
            title_url = entry["titleUrl"]
            artist = entry["subtitles"][0]["name"].replace(" - Topic", "")
            artist_title = (artist, title, title_url)

            if artist_title in pruned:
                pruned[artist_title] = pruned[artist_title] + 1
            else:
                pruned[artist_title] = 1

        if entry["header"] == "YouTube":
            total_watches += 1
            if "https://www.youtube.com/watch?v=" in entry["title"]:
                # Extract the channel name from the URL
                channel_name = entry["title"].split("channel/")[-1].split("/")[0]
                top_channels[channel_name] += 1

    # Create a bar chart
    sorted_dict = dict(sorted(pruned.items(), key=lambda item: (item[1], item[0]), reverse=True))
    sorted_items = list(sorted_dict.items())
    sorted_items = sorted(sorted_items, key=lambda x: x[1], reverse=True)
    top_items = sorted_items[:10]

    df = pd.DataFrame(top_items, columns=['ArtistTitle', 'Listens'])
    df[['Artist', 'Title', 'TitleUrl']] = pd.DataFrame(df['ArtistTitle'].to_list(), index=df.index)
    df.drop(columns=['ArtistTitle'], inplace=True)

    fig = px.bar(df, x='Listens', y='Artist', text='Title', title='Top 10 Tracks by Listens')
    fig.update_traces(texttemplate='%{text}', textposition='outside')

    chart_html = pio.to_html(fig, full_html=False)

    return chart_html, total_watches, top_channels

def create_history_list_from_json(json_data):
    # Parse the JSON data
    history_data = json.loads(json_data)

    # Create a list of dictionaries for YouTube videos
    history_list = []
    for entry in history_data:
        if entry.get('header') == 'YouTube':
            title_url = entry.get('titleUrl')
            if title_url:
                video_id = title_url.split('=')[1]
                view_date = entry.get('time')

                # Check for 'From Google Ads' and skip if found
                details = entry.get('details', [])
                if any(d.get('name') == 'From Google Ads' for d in details):
                    continue

                history_list.append({
                    'watch_date': view_date,
                    'video_id': video_id
                })

    return history_list
    
def get_video_stats(youtube, sample_list):
    all_data = []
    all_ids = [sub['video_id'] for sub in sample_list]
    batched_ids = []
    n = 50
    for i in range(0,len(all_ids),n):
        batched_ids.append(all_ids[i:i + n])

    for i in range(len(batched_ids)):
        request = youtube.videos().list(
                    part='snippet,contentDetails,statistics',
                    id=batched_ids[i])

        response = request.execute()

        for i in range(len(response["items"])):
            data = dict(video_id = response["items"][i]["id"],
                    video_title = response["items"][i]["snippet"]['title'],
                    video_description = response["items"][i]["snippet"]['description'],
                    published_at = response["items"][i]["snippet"]['publishedAt'],
                    channel_id = response["items"][i]["snippet"]['channelId'],
                    category_id = response["items"][i]["snippet"]['categoryId'],
                    duration = response["items"][i]["contentDetails"]['duration'],
                    favorite_count = response["items"][i]["statistics"]['favoriteCount']
                    )
            if 'tags' in response["items"][i]["snippet"]:
             data['tag'] = response["items"][i]["snippet"]['tags']
            else:
             data['tag'] = 'NULL'

            if 'likeCount' in response["items"][i]["statistics"]:
             data['like_count'] = response["items"][i]["statistics"]['likeCount']
            else:
             data['like_count'] = 'NULL'

            if 'commentCount' in response["items"][i]["statistics"]:
             data['comment_count'] = response["items"][i]["statistics"]['commentCount']
            else:
             data['comment_count'] = 'NULL'

            if 'viewCount' in response["items"][i]["statistics"]:
             data['view_count'] = response["items"][i]["statistics"]['viewCount']
            else:
             data['view_count'] = 'NULL'
            if data['video_title'] is None:
                print(i)
            all_data.append(data)
    return all_data

def generate_watchday_visualization(nofvwbwd):
    # Create a copy of the data
    day_data = nofvwbwd
    days = [ 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    final_data_groupedby_watch_day = day_data.groupby(['watch_date'])['watch_date'].size().reset_index(name='count')
    final_data_groupedby_watch_day['watch_date'] = pd.Categorical(final_data_groupedby_watch_day['watch_date'], categories=days, ordered=True)
    final_data_groupedby_watch_day = final_data_groupedby_watch_day.sort_values('watch_date')


    # Your data
    counts = final_data_groupedby_watch_day['count']
    labels = final_data_groupedby_watch_day['watch_date']

    max_index = counts.idxmax()
    pull = [0.1 if i == max_index else 0 for i in range(len(counts))]

    # Create a Pie chart
    fig_pie = go.Figure()
    fig_pie.add_trace(go.Pie(labels=labels, values=counts, pull=pull, textinfo='percent+label',
                            marker=dict(line=dict(color='black', width=2))))

    fig_pie.update_layout(
        title='Number Of Videos Watched By Weekday (Pie Chart)',
        font=dict(color='black', size=16)
    )

    return fig_pie

def process_and_plot_top_channels(final_data_clean, youtube, max_duration=14400, min_total_duration=1000, top_n=10):
    # Convert 'max_duration' to a timedelta with the same units (seconds)
    max_duration_timedelta = timedelta(seconds=max_duration)

    # Filter videos by duration
    final_data_groupedby_channel = final_data_clean[final_data_clean['duration_sec'] < max_duration_timedelta].copy()
    
    # Convert duration_sec to float (number of seconds) for rounding
    final_data_groupedby_channel['duration_sec'] = final_data_groupedby_channel['duration_sec'].dt.total_seconds()
    
    # Calculate video duration in minutes
    final_data_groupedby_channel['duration_min'] = final_data_groupedby_channel['duration_sec'].div(60).round(2)
    
    # Group data by channel and calculate total duration
    final_data_groupedby_channel = final_data_groupedby_channel.groupby(['channel_id'])['duration_min'].sum().reset_index(name='sum')
    
    # Filter channels with total duration greater than a threshold
    final_data_groupedby_channel = final_data_groupedby_channel[final_data_groupedby_channel['sum'] > min_total_duration]
    
    # Retrieve channel titles using YouTube API
    def get_channel_title(cid):
        request1 = youtube.channels().list(
                        part='snippet,contentDetails,statistics',
                        id=cid)

        response = request1.execute()
        title = response['items'][0]['snippet']['title']
        return title
    
    final_data_groupedby_channel['channel_title'] = final_data_groupedby_channel['channel_id'].apply(get_channel_title)
    
    # Sort the DataFrame by the 'sum' column in descending order and select the top N rows
    final_data_groupedby_channel = final_data_groupedby_channel.sort_values(by='sum', ascending=False).head(top_n)
    
    # Create a horizontal bar chart
    fig = go.Figure()
    color_palette = px.colors.sequential.Reds[::-1]
    fig.add_trace(go.Bar(
        y=final_data_groupedby_channel['channel_title'],
        x=final_data_groupedby_channel['sum'],
        orientation='h',
        marker=dict(color=color_palette),
        text=final_data_groupedby_channel['sum'],
        textposition='inside',
    ))
    
    fig.update_layout(
        title=f'Top {top_n} Favorite Channels By View Time (minutes)',
        xaxis_title='Total View Time (minutes)',
        yaxis_title='Channel name',
        yaxis_showticklabels=True,
        xaxis_showticklabels=True,
        yaxis_ticks='outside',
        yaxis_ticklen=5,
        showlegend=False,
    )
    
    fig.update_xaxes(tickangle=-80)
    
    return fig
    
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    file_content = session.get('uploaded_file')
    if file_content:
        return redirect('/process')

    if request.method == 'POST':
        uploaded_file = request.files['file']
        if uploaded_file:
            # Store the uploaded file in session
            session['uploaded_file'] = uploaded_file.read()
            return redirect('/process')

    return render_template('upload.html')

@app.route('/process')
def process_file():
    file_content = session.get('uploaded_file')
    yt_chart_html = session.get('yt_chart_html')
    yt_total_watches = session.get('yt_total_watches')
    yt_top_channels = session.get('yt_top_channels')
    yt_history_list = session.get('yt_history_list')
    yt_video_stats = session.get('yt_video_stats')
    yt_final_data_groupedby_category = session.get('yt_final_data_groupedby_category')
    nofvwbyc = session.get('nofvwbyc')
    nofvwbwd = session.get('nofvwbwd')
    top_channels = session.get('top_channels')

    if file_content is None:
        return redirect('/upload')

    if yt_chart_html is None or yt_total_watches is None or yt_top_channels is None:
        app.logger.info("1st block none")
        yt_chart_html, yt_total_watches, yt_top_channels = process_uploaded_file(file_content)
        session['yt_chart_html'] = yt_chart_html
        session['yt_total_watches'] = yt_total_watches
        session['yt_top_channels'] = yt_top_channels
        
    if nofvwbyc is None:
        app.logger.info("nofvwbyc is None")
    if yt_history_list is None:
        app.logger.info("yt_history_list is None")
    if yt_video_stats is None:
        app.logger.info("yt_video_stats is None")
    if nofvwbwd is None:
        app.logger.info("nofvwbwd is None")
    if top_channels is None:
        app.logger.info("top_channels is None ")

    
    # Now you know which variables are None, and you can add additional logic or handle them as needed.
    if nofvwbyc is None or yt_history_list is None or yt_video_stats is None or nofvwbwd is None or top_channels is None:
        app.logger.info("2nd block none")
        youtube = build('youtube', 'v3', developerKey=api_key)
        history_list = create_history_list_from_json(file_content)
        session['yt_history_list'] = history_list
        video_stats = get_video_stats(youtube, history_list)
        session['yt_video_stats'] = video_stats
        video_data = pd.DataFrame(video_stats)
        video_view = pd.DataFrame(history_list)
        final_data = video_view.merge(video_data, how='left', on='video_id')
        final_data_clean = final_data.dropna().copy() #Remove NAs
        final_data_clean = final_data_clean.drop_duplicates(['watch_date']) #remove duplicates
        numeric_cols = ['view_count','like_count','favorite_count','comment_count']
        final_data_clean[numeric_cols] = final_data_clean[numeric_cols].apply(pd.to_numeric, errors='coerce',axis = 1) # from object to number
        final_data_clean['watch_date'] = final_data_clean['watch_date'].apply(parse_date)
        final_data_clean['published_at'] = final_data_clean['published_at'].apply(parse_date)
        final_data_clean['duration_sec'] = final_data_clean['duration'].apply(lambda x: isodate.parse_duration(x)) # new column for Duration in seconds
        final_data_clean['duration_sec'] = final_data_clean['duration_sec'].astype('timedelta64[s]')
        final_data_clean.dtypes
        final_data_clean.isnull().any()
        final_data_clean['category_id'] = final_data_clean['category_id'].replace(['2', '1','10','15','17','18','19','20','21','22','23','24','25','26','27','28','29','30','31','32','33','34','35','36','37','38','39','40','41','42','43','44'],
                                                                              ['Autos & Vehicles','Film & Animation', 'Music', 'Pets & Animals', 'Sports', 'Short Movies',
                                                                               'Travel & Events', 'Gaming', 'Videoblogging', 'People & Blogs', 'Comedy', 'Entertainment',
                                                                               'News & Politics', 'How to & Style', 'Education', 'Science & Technology', 'Nonprofits & Activism', 'Movies',
                                                                               'Anime/Animation', 'Action/Adventure', 'Classics','Comedy', 'Documentary', 'Drama', 'Family', 'Foreign',
                                                                               'Horror', 'Sci-Fi/Fantasy', 'Thriller', 'Shorts', 'Shows', 'Trailers'])
        final_data_groupedby_category = final_data_clean.groupby(['category_id'])['category_id'].size().reset_index(name='counts')  #group by category
        final_data_groupedby_category = final_data_groupedby_category.sort_values(by=['counts'],ascending=False).reset_index(drop=True) #sort by counts
        science_technology_educational_videos = final_data_clean[np.logical_or(final_data_clean['category_id'] == 'Science & Technology' , final_data_clean['category_id'] == 'Education')]
        pd.set_option('display.max_colwidth', 100)
        final_data_groupedby_category = final_data_groupedby_category.sort_values(by='counts', ascending=True)
        session['yt_final_data_groupedby_category'] = final_data_groupedby_category
        color_scale = [[0, 'lightpink'],[0.5, 'lightcoral'],[1, 'red']]
        fig = go.Figure()
        # Add horizontal bars with the gradient color scale
        fig.add_trace(go.Bar(
            y=final_data_groupedby_category['category_id'],
            x=final_data_groupedby_category['counts'],
            orientation='h',
            marker=dict(color=final_data_groupedby_category['counts'], colorbar=dict(title='Counts'), colorscale=color_scale),
            text=final_data_groupedby_category['counts'],
            textposition='outside',
        ))
        fig.update_layout(
            xaxis_title='',
            yaxis_title='',
            xaxis_showticklabels=False,
            yaxis_showticklabels=True,
            yaxis_ticks='outside',
            yaxis_ticklen=5,
            showlegend=False,
            title='Number Of Videos Watched By Category',
        )
        nofvwbyc = fig.to_html(full_html=False)
        session['nofvwbyc'] = nofvwbyc
        day_data = final_data_clean.copy()
        day_data['watch_date'] = pd.to_datetime(day_data['watch_date'], utc=True)
        day_data['watch_date'] = day_data['watch_date'].dt.day_name()
        fig_pie = generate_watchday_visualization(day_data)
        nofvwbwd = fig_pie.to_html(full_html=False, default_height=500, default_width=700)
        session['nofvwbwd'] = nofvwbwd
        top_channels = process_and_plot_top_channels(final_data_clean, youtube)
        top_channels = top_channels.to_html(full_html=False)
        session['top_channels'] = top_channels
        
    return render_template('results.html', chart_html=yt_chart_html,
                           total_watches=yt_total_watches, top_channels=yt_top_channels, nofvwbyc=nofvwbyc, nofvwbwd=nofvwbwd, w_top_channels=top_channels)
    
def generate_chart(df):
    # Define the features to include in the chart
    features = ['Danceability', 'Energy', 'Loudness', 'Speechiness', 'Acousticness',
                'Instrumentalness', 'Liveness', 'Valence']

    # Group the DataFrame by playlist and calculate the mean values of each feature
    df = df.groupby(['Playlist'])[features].mean().reset_index()

    # Calculate the mean values of the audio features for the entire playlist
    danceability = df['Danceability'].mean()
    energy = df['Energy'].mean()
    loudness = df['Loudness'].mean()
    speechiness = df['Speechiness'].mean()
    acousticness = df['Acousticness'].mean()
    instrumentalness = df['Instrumentalness'].mean()
    liveness = df['Liveness'].mean()
    valence = df['Valence'].mean()

    # Generate a message based on the audio features

    if valence >= 0.8 and energy >= 0.8 and danceability >= 0.7:
        message = 'Your Spotify playlist is perfect for getting pumped up and feeling good! The high valence, energy, and danceability levels make for a super fun listening experience!'
    elif acousticness >= 0.7 and instrumentalness >= 0.7 and valence >= 0.5:
        message = 'Based on your listening habits, it looks like you prefer relaxing and chill songs that are perfect for unwinding after a long day! Your Spotify playlist has plenty of mellow tracks that are great for relaxing.'
    elif speechiness >= 0.7 and energy >= 0.6:
        message = 'Your Spotify playlist has plenty of powerful and energetic music with strong beats and heavy bass! These songs are perfect for working out or pushing yourself to the limit.'
    elif energy >= 0.8 and loudness >= 0.6 and speechiness >= 0.4:
        message = 'Your Spotify playlist is full of high-energy tracks with great beats and powerful vocals! These songs are perfect for getting pumped up and ready to take on the day.'
    elif valence <= 0.3 and acousticness >= 0.7:
        message = 'Your Spotify playlist has a lot of moody, atmospheric songs that are perfect for introspection and reflection. With high acousticness levels and low valence scores, these tracks are great for setting a mellow and contemplative mood.'
    elif valence >= 0.5 and liveness >= 0.6:
        message = 'Your Spotify playlist has lots of live music recordings that capture the energy and excitement of a live performance! With high liveness levels and moderate to high valence scores, these tracks are perfect for feeling the thrill of being at a concert.'
    elif instrumentalness <= 0.3 and danceability >= 0.7 and speechiness >= 0.4:
        message = 'Your Spotify playlist is full of upbeat, danceable tracks with catchy lyrics and hooks! With low instrumentalness levels and high danceability and speechiness scores, these songs are perfect for singing along and getting your groove on.'
    elif energy <= 0.3 and speechiness <= 0.3 and danceability <= 0.3:
        message = 'Your Spotify playlist has a lot of slow and relaxing songs that are perfect for winding down and getting some rest. These tracks have low energy, speechiness, and danceability levels, making them great for calming the mind and body.'
    elif acousticness >= 0.8 and liveness <= 0.2:
        message = 'Your Spotify playlist has a lot of soft and gentle songs that are perfect for creating a cozy and intimate atmosphere. With high acousticness and low liveness levels, these tracks are great for setting a romantic or peaceful mood.'
    elif valence < 0.5 and energy < 0.5 and danceability < 0.5:
        message = 'Your Spotify playlist contains songs with low energy, low valence, and low danceability. These tracks are often more introspective and downbeat, and can be perfect for quiet reflection or relaxation.'
    elif instrumentalness >= 0.7 and speechiness <= 0.3:
        message = 'Your Spotify playlist has a lot of instrumental music with minimal vocals that is great for focusing or studying! With high instrumentalness levels and low speechiness scores, these tracks can help you concentrate and stay productive.'
    elif danceability >= 0.8 and valence >= 0.6:
        message = 'Your Spotify playlist is full of energetic and upbeat songs with positive lyrics and catchy hooks! With high danceability and valence scores, these tracks are perfect for feeling happy and carefree.'
    else:
        message = 'You have a diverse range of music in your Spotify playlist that spans multiple genres and styles. Keep exploring new artists and songs to add even more variety!'

    print(message)

    # Create a polar chart of the audio features for each playlist and update the chart layout to include the message
    fig = go.Figure()
    for index, row in df.iterrows():
        fig.add_trace(go.Scatterpolar(
            r=row[features].tolist(),
            theta=features,
            fill='toself',
            name=row['Playlist'],
            hovertemplate="%{r:.2f}"
        ))

    fig.update_layout(
        template='seaborn',
        polar=dict(
            radialaxis=dict(showticklabels=False, ticks='', range=[0, 1])
        ),
        margin=dict(r=0),
        title="Playlist audio features Polar Diagram"
    )

    return fig, message

# Route to display the form for entering playlist information
@app.route('/pg')
def pg():
    return render_template('pg.html')


# Route to generate the chart
@app.route('/generate-csv', methods=['POST'])
def generate_chart_route():
    # Get the access token from the user's session
    access_token = get_access_token(session, auth_manager)
    if access_token is None:
        return "token is missing. Please authenticate with Spotify."

    # Create Spotipy object with the authenticated access token
    sp = spotipy.Spotify(auth=access_token, requests_timeout=60)

    # Get the playlists entered by the user
    playlists = {}
    i = 0
    while True:
        name = request.form.get(f'name{i}')
        url = request.form.get(f'url{i}')
        if not name or not url:
            break  # Stop when no more entries are found
        playlists[name] = url
        i += 1

    # Create an empty DataFrame to store the track information
    df = pd.DataFrame(columns=[
        ('Playlist', str),
        ('Track Name', str),
        ('Artist', str),
        ('Album', str),
        ('URI', str),
        ('Danceability', float),
        ('Energy', float),
        ('Key', int),
        ('Loudness', float),
        ('Mode', int),
        ('Speechiness', float),
        ('Acousticness', float),
        ('Instrumentalness', float),
        ('Liveness', float),
        ('Valence', float),
        ('Tempo', float),
        ('Duration', int),
        ('Genre', str)
    ])

    # Iterate over the playlists dictionary
    for name, playlist_url in playlists.items():
        # Get the playlist ID from the URL
        playlist_id = playlist_url.split(':')[2]
        # Use the playlist ID to get the tracks in the playlist
        results = sp.playlist_tracks(playlist_id)
        # Iterate over the results to get the track information
        for item in results['items']:
            track = item['track']
            # Use the track URI to get more detailed audio features for the track
            audio_features = sp.audio_features(track['uri'])[0]
            # Use the artist name to get the genre of each artist
            artists = [artist['name'] for artist in track['artists']]
            genres = []
            for artist in artists:
                result = sp.search(q='artist:' + artist, type='artist')
                if len(result['artists']['items']) > 0:
                    genres.extend(result['artists']['items'][0]['genres'])
            # Join the list of genres into a comma-separated string
            genres_str = ', '.join(genres)
            # Add the track information to the DataFrame, including the new audio features and genre information
            df = pd.concat([df, pd.DataFrame({
                'Playlist': name,
                'Track Name': track['name'],
                'Artist': ', '.join(artists),
                'Album': track['album']['name'],
                'URI': track['uri'],
                'Danceability': float(audio_features['danceability']),
                'Energy': float(audio_features['energy']),
                'Key': int(audio_features['key']),
                'Loudness': float(audio_features['loudness']),
                'Mode': int(audio_features['mode']),
                'Speechiness': float(audio_features['speechiness']),
                'Acousticness': float(audio_features['acousticness']),
                'Instrumentalness': float(audio_features['instrumentalness']),
                'Liveness': float(audio_features['liveness']),
                'Valence': float(audio_features['valence']),
                'Tempo': float(audio_features['tempo']),
                'Duration': int(audio_features['duration_ms']),
                'Genre': genres_str,
            }, index=[0])], ignore_index=True)

    # Generate the polar chart of audio features and sentiment analysis message
    fig, message = generate_chart(df)

    # Convert the chart to HTML
    chart_html = fig.to_html(full_html=False, default_height=500, default_width=700)

    # Render the HTML template with the chart and message
    return render_template('pgv.html', chart=chart_html, message=message)

def parse_timestamp(timestamp):
    formats_to_try = ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"]
    
    for format_str in formats_to_try:
        try:
            return pd.to_datetime(timestamp, format=format_str)
        except ValueError:
            pass

def generate_recently_played_chart(sp):
    # Retrieve the user's recently played data
    recently_played_data = sp.current_user_recently_played()
    
    if len(recently_played_data['items']) == 0:
        return None  # No data to display

    # Parse track data and group by timestamp (hour)
    timestamps = [item['played_at'] for item in recently_played_data['items']]
    timestamps = [parse_timestamp(ts) for ts in timestamps]
    # Convert the list of timestamps to a Pandas Series
    timestamps = pd.Series(timestamps)
    # Round the timestamps to the nearest hour
    timestamps = timestamps.dt.floor('H')
    counts = timestamps.value_counts()
    # Format timestamps as strings in "%I %p" format (e.g. "12 PM")
    labels = [dt.strftime("%I %p") for dt in counts.index]

    # Create Plotly figure with listening history data
    fig = go.Figure(data=[go.Pie(values=counts, labels=labels)])
    fig.update_layout(title='Listening History Over Time')
    fig.update_traces(hole=.4, hoverinfo="label+value", marker=dict(line=dict(color='white', width=2)))
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color="black")  # Set both plot and paper background to black

    return fig

@app.route('/spowrpart')
def spowrpart():
    access_token = get_access_token(session, auth_manager)
    if access_token is None:
        return "token is missing. Please authenticate with Spotify."

    # Create Spotipy object with the authenticated access token
    sp = spotipy.Spotify(auth=access_token, requests_timeout=40)
    top_artists = sp.current_user_top_artists(limit=5, offset=0, time_range='medium_term')
    html_template = generate_top_artists_html(top_artists)
    return render_template_string(html_template)

@app.route('/spowrptrc')
def spowrptrc():
    access_token = get_access_token(session, auth_manager)
    if access_token is None:
        return "token is missing. Please authenticate with Spotify."

    # Create Spotipy object with the authenticated access token
    sp = spotipy.Spotify(auth=access_token, requests_timeout=40)
    top_tracks = sp.current_user_top_tracks(limit=5, offset=0, time_range='medium_term')
    html_template = generate_top_tracks_html(top_tracks)
    return render_template_string(html_template)

@app.route('/current_song')
def current_song():
    # Get the access token from the user's session
    access_token = get_access_token(session, auth_manager)
    if access_token is None:
        return "token is missing. Please authenticate with Spotify."

    # Create Spotipy object with the authenticated access token
    sp = spotipy.Spotify(auth=access_token, requests_timeout=40)

    # Try to get the user's currently playing track
    currently_playing_data = sp.current_user_playing_track()

    if currently_playing_data is not None:
        # If the user is currently playing something, extract the song and artist names
        song_name = currently_playing_data['item']['name']
        artist_name = currently_playing_data['item']['artists'][0]['name']

        # Extract the Spotify track URI from the currently playing track data
        spotify_track_uri = currently_playing_data['item']['uri'].split(":")[-1]

        playing_status = f'{song_name} by {artist_name}'

    else:
        # If the user is not currently playing anything, get their recently played tracks
        recently_played_data = sp.current_user_recently_played()

        if len(recently_played_data['items']) > 0:
            # If there are recently played tracks, extract the most recent one's song and artist names
            last_played_data = recently_played_data['items'][0]
            song_name = last_played_data['track']['name']
            artist_name = last_played_data['track']['artists'][0]['name']

            # Extract the Spotify track URI from the most recently played track data
            spotify_track_uri = last_played_data['track']['uri'].split(":")[-1]

            playing_status = f'{song_name} by {artist_name}'
            seed_tracks = [spotify_track_uri]
            limit = 10
            recommended_tracks = sp.recommendations(seed_tracks=seed_tracks, limit=limit)
            track_details_list = []
            for track in recommended_tracks['tracks']:
                track_details = {'track_name': track['name'],'artist': track['artists'][0]['name'],'spotify_url': track['external_urls']['spotify'],'preview_url': track['preview_url']}
                # Extract the track ID from the Spotify URL
                track_url = track['external_urls']['spotify']
                track_id = track_url.split('/')[-1]
                track_details['track_id'] = track_id  # Add the track ID to the details
                track_details_list.append(track_details)
        else:
            # If there are no recently played tracks or currently playing track, set a default status
            playing_status = None

    # Render the HTML template and pass the playing status and Spotify track URI data to it
    return render_template('cr.html', playing_status=playing_status, spotify_track_uri=spotify_track_uri, track_details_list=track_details_list)

def get_user_top_tracks_with_audio_features(sp, limit=50):
    # Create an empty list to hold DataFrames for each time range
    dfs = []

    # Iterate over time ranges and retrieve top tracks with audio features for each
    for time_range in ('short_term', 'medium_term', 'long_term'):
        top_tracks = sp.current_user_top_tracks(limit=limit, time_range=time_range)

        # Create an empty list to hold audio features data for the current time range
        audio_features_list = []

        for i, track in enumerate(top_tracks['items']):
            # Retrieve the audio features for the track
            audio_features = sp.audio_features(track['id'])[0]

            # Additional information
            audio_features['Index'] = i + 1
            audio_features['Track Name'] = track['name']
            audio_features['Artist'] = track['artists'][0]['name']
            audio_features['Album'] = track['album']['name']
            audio_features['Release Date'] = track['album']['release_date']
            audio_features['Popularity'] = track['popularity']

            # Get artist information to include genres
            artist_info = sp.artist(track['artists'][0]['id'])
            audio_features['Genres'] = ','.join(artist_info['genres'])

            # Append the audio features to the list for the current time range
            audio_features_list.append(audio_features)

        # Create a DataFrame from the audio features list for the current time range
        df = pd.DataFrame(audio_features_list)

        # Reorder the columns in the DataFrame
        df['Rank'] = df['Popularity'].rank(method='min', ascending=False)
        df = df[['Rank', 'Track Name', 'Artist', 'Album', 'Genres', 'Release Date', 'Popularity']]
        
        # Add the time range label to the DataFrame
        df['Time Range'] = time_range

        # Append the DataFrame to the list of DataFrames
        dfs.append(df)

    return dfs

# Define a function to create and display the plots
def create_and_show_plots(dfs):
    plots = []

    for df in dfs:
        fig = px.bar(df, x='Rank', y='Artist', text='Track Name', title=f'Top Tracks by Popularity ({df["Time Range"].iloc[0]})')
        fig.update_xaxes(title_text='Popularity')
        fig.update_yaxes(title_text='Artist')
        # Customize the appearance
        fig.update_traces(marker_color='purple')
        fig.update_traces(textfont_color='white')  # Set text color to white
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color="black")  # Set both plot and paper background to black
        fig.update_layout(template="plotly_white")
        plots.append(fig)

    return plots


def get_user_top_albums_with_figures(sp, time_ranges, limit=10):
    figures = []

    for time_range in time_ranges:
        df = get_user_top_albums(sp, time_range=time_range, limit=limit)
        
        if not df.empty:
            # Create a Plotly bar plot with customized appearance
            fig = px.bar(df, x='Popularity', y='Artist', text='Album Name', title=f'Top Artist by Album Popularity ({time_range}')
            fig.update_xaxes(title_text='Popularity')
            fig.update_yaxes(title_text='Artist')

            # Customize the appearance
            fig.update_traces(marker_color='maroon')
            fig.update_traces(textfont_color='white')  # Set text color to white
            fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color="black")  # Set both plot and paper background to black
            fig.update_layout(template="plotly_white")
            figure_html = pyo.plot(fig, include_plotlyjs=False, output_type='div')
            figures.append(figure_html)

    return df, figures

def get_user_top_albums(sp, time_range='medium_term', limit=50):
    # Get the user's top albums from the Spotify API
    top_albums = sp.current_user_top_tracks(limit=limit, time_range=time_range)

    # Create an empty list to hold the details for each album
    album_details_list = []

    # Keep track of unique album names to remove duplicates
    unique_albums = set()

    # Iterate over the user's top albums and retrieve their details
    for i, track in enumerate(top_albums['items']):

        # Retrieve the details for the album
        album_name = track['album']['name']
        if album_name not in unique_albums:
            album_details = {}
            album_details['Album Name'] = album_name
            album_details['Artist'] = track['artists'][0]['name']
            album_details['Release Date'] = track['album']['release_date']
            album_details['Total Tracks'] = track['album']['total_tracks']
            album_details['Popularity'] = track['popularity']
            album_details['Genres'] = ','.join(sp.artist(track['artists'][0]['id'])['genres'])
            
            # Add the album details dictionary to the list and mark the album as seen
            album_details_list.append(album_details)
            unique_albums.add(album_name)

    # Convert list of dictionaries to Pandas DataFrame
    df = pd.DataFrame(album_details_list)

    # Add a new column to the DataFrame that ranks the albums by their popularity score
    df['Rank'] = df['Popularity'].rank(method='min', ascending=False)
    return df


# Function to retrieve user's top artists for a given time range
def get_user_top_artists(sp, time_range='medium_term', limit=50):
    # Get the user's top artists from the Spotify API
    top_artists = sp.current_user_top_artists(limit=limit, time_range=time_range)

    # Create an empty list to hold the details for each artist
    artist_details_list = []

    # Iterate over the user's top artists and retrieve their details
    for i, artist in enumerate(top_artists['items']):
        # Retrieve the details for the artist
        artist_details = {}
        artist_details['Artist ID'] = artist['id']
        artist_details['Artist Name'] = f'<a href="{artist["external_urls"]["spotify"]}">{artist["name"]}</a>'
        artist_details['Genres'] = ','.join(artist.get('genres', ['Unknown Genres']))
        artist_details['Popularity'] = artist.get('popularity', 'Unknown Popularity')

        # Add the artist details dictionary to the list
        artist_details_list.append(artist_details)

    # Convert list of dictionaries to Pandas DataFrame
    df = pd.DataFrame(artist_details_list)

    # Add a new column to the DataFrame that displays the artist ranking as 1-2-3
    #df['Index'] = df.index + 1
    df['Rank'] = df['Popularity'].rank(method='min', ascending=False)

    # Reorder the columns in the DataFrame
    df = df[['Rank', 'Artist ID', 'Artist Name', 'Genres', 'Popularity']]

    # Split the DataFrame into separate DataFrames for each time range
    short_term_df = df.copy()
    medium_term_df = df.copy()
    long_term_df = df.copy()

    # Append the DataFrames to a list
    dfs = [medium_term_df, long_term_df]

    # Return the list of DataFrames
    return dfs

def get_user_top_artists_with_details(sp, limit=50):
    # Create an empty list to hold artist details DataFrames for each time range
    dfs = []

    # Iterate over time ranges and retrieve top artists' details for each
    for time_range in ('medium_term', 'long_term'):
        # Get the user's top artists and their details
        top_artists = sp.current_user_top_artists(limit=limit, time_range=time_range)

        # Create a list to hold artist details data for the current time range
        artist_details_list = []

        for i, artist in enumerate(top_artists['items']):
            # Retrieve the artist's details
            artist_details = {}
            artist_details['Rank'] = i + 1
            artist_details['Artist Name'] = artist['name']
            artist_details['Genres'] = ','.join(artist.get('genres', ['Unknown Genres']))
            artist_details['Popularity'] = artist.get('popularity', 'Unknown Popularity')

            # Append the artist details to the list for the current time range
            artist_details_list.append(artist_details)

        # Create a DataFrame from the artist details list for the current time range
        df = pd.DataFrame(artist_details_list)

        # Reorder the columns in the DataFrame
        df = df[['Rank', 'Artist Name', 'Genres', 'Popularity']]

        # Add the time range label to the DataFrame
        df['Time Range'] = time_range

        # Append the DataFrame to the list of DataFrames
        dfs.append(df)

    return dfs

def create_and_show_artist_plots(dfs):
    plots = []

    for df in dfs:
        fig = px.bar(df, x='Rank', y='Artist Name', text='Genres', title=f'Top Artists by Popularity ({df["Time Range"].iloc[0]})')
        fig.update_xaxes(title_text='Popularity')
        fig.update_yaxes(title_text='Artist Name')
        # Customize the appearance
        fig.update_traces(marker_color='teal')
        fig.update_traces(textfont_color='white')  # Set text color to white
        fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color="black")  # Set both plot and paper background to black
        fig.update_layout(template="plotly_white")
        plots.append(fig)

    return plots

def get_user_top_tracks_by_decade(sp, limit=50):
    # Get user's top tracks for the long-term time range and offset
    top_tracks = sp.current_user_top_tracks(limit=limit, time_range='long_term')

    # Create empty list to hold track release year
    years = []

    # Iterate over the user's top tracks and retrieve their album release date
    for i, track in enumerate(top_tracks['items']):
        album = sp.album(track['album']['id'])
        years.append(int(album['release_date'][:4]))

    # Convert list of years to Pandas Series
    years_series = pd.Series(years)

    # Bin the years by decade
    decades = pd.cut(years_series, bins=range(1960, 2031, 10), labels=[f"{decade}s" for decade in range(1960, 2030, 10)])

    # Count the number of tracks in each decade
    track_counts = decades.value_counts().sort_index()

    fig = px.bar(track_counts, x=track_counts.values, y=track_counts.index, orientation='h', title='Top Tracks by Decade')
    fig.update_xaxes(title_text='Play Count')
    fig.update_yaxes(title_text='Decade')
    fig.update_traces(marker_color='green')
    fig.update_traces(textfont_color='white')  # Set text color to white
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', font_color="black")  # Set both plot and paper background to black
    fig.update_layout(template="plotly_white")
    return fig

@app.route('/newx')
def newx():
    # Get the access token from the user's session
    access_token = get_access_token(session, auth_manager)
    if access_token is None:
        return "token is missing. Please authenticate with Spotify."

    # Create Spotipy object with the authenticated access token
    sp = spotipy.Spotify(auth=access_token, requests_timeout=40)
    
    user_info = get_user_basic_info(sp)
    display_name = user_info['display_name']
    email = user_info['email']
    followers = user_info['followers']
    country = user_info['country']
    profile_picture = user_info['profile_picture']

    # Check if the data is already in the session
    chart_html = session.get('recently_played_chart')
    graph_div = session.get('user_top_tracks')
    figures = session.get('figures')
    utop_tracks = session.get('utop_tracks')
    utop_artists = session.get('utop_artists')

    if figures is None:
        time_ranges = ['short_term', 'medium_term', 'long_term']
        df, figures = get_user_top_albums_with_figures(sp, time_ranges, limit=10)
        session['figures'] = figures

    if utop_tracks is None:
        dfs = get_user_top_tracks_with_audio_features(sp, limit=10)
        utop_tracks = create_and_show_plots(dfs)
        utop_tracksx = [df.to_html(full_html=False) for df in utop_tracks]
        session['utop_tracks'] = utop_tracksx

    if utop_artists is None:
        dfs = get_user_top_artists_with_details(sp, limit=10)
        utop_artists = create_and_show_artist_plots(dfs)
        utop_artistsx = [df.to_html(full_html=False) for df in utop_artists]
        session['utop_artists'] = utop_artistsx

    return render_template('newx.html', display_name=display_name, email=email, followers=followers, country=country, user_profile_picture=profile_picture, figures=figures, utop_tracks=utop_tracks, utop_artists=utop_artists)


@app.route('/tdr')
def tdr():
    # Get the access token from the user's session
    access_token = get_access_token(session, auth_manager)
    if access_token is None:
        return "token is missing. Please authenticate with Spotify."

    # Create Spotipy object with the authenticated access
    sp = spotipy.Spotify(auth=access_token, requests_timeout=40)
    chart_html = session.get('recently_played_chart')
    graph_div = session.get('user_top_tracks')
    if chart_html is None:
        rp = generate_recently_played_chart(sp)
        chart_htmlx = rp.to_html(full_html=False)
        session['recently_played_chart'] = chart_htmlx

    if graph_div is None:
        track_counts = get_user_top_tracks_by_decade(sp)
        graph_divx = track_counts.to_html(full_html=False)
        session['user_top_tracks'] = graph_divx
        
    return render_template('rp.html', chart=chart_html, graph=graph_div)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)