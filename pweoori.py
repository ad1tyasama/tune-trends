import datetime

def generate_top_artists_html(top_artists):
    # Create an HTML template for displaying the top artists
    html_template = """
    <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="shortcut icon" type="image/x-icon" href="https://dishapatel010.github.io/T.png">
    <title>Top Artists</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f0f0f0;
            margin: 0;
            padding: 0;
        }

        header {
            background-color: #1DB954;
            color: white;
            text-align: center;
            padding: 1rem;
            font-size: 1.5rem;
        }

        main {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            padding: 1rem;
        }

        .artist-card {
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 10px;
            margin: 1rem;
            max-width: 300px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            animation: fadeIn 1s ease-in-out;
        }

        .artist-image {
            width: 100%;
            max-height: 200px;
            object-fit: cover;
        }

        h2 {
            font-size: 1.5rem;
            margin: 0.5rem;
        }

        p {
            font-size: 1.2rem;
            margin: 0.5rem;
        }

        a {
            text-decoration: none;
            color: #1DB954;
            transition: color 0.2s;
        }

        a:hover {
            color: #0D652D;
        }

        @keyframes fadeIn {
            0% {
                opacity: 0;
            }
            100% {
                opacity: 1;
            }
        }
    </style>
</head>
<body>
    <header>
        <h1>Your Top 5 Artists</h1>
    </header>
    <main>
    """

    # Add artist cards to the HTML template
    for idx, artist in enumerate(top_artists['items'], start=1):
        artist_name = artist['name']
        artist_url = artist['external_urls']['spotify']
        artist_image_url = artist['images'][0]['url']

        html_template += f"""
        <div class="artist-card">
            <a href="{artist_url}" target="_blank">
                <img class="artist-image" src="{artist_image_url}" alt="{artist_name}">
            </a>
            <h2>{artist_name}</h2>
        </div>
        """

    # Close the HTML template
    html_template += """
        </main>
    </body>
    </html>
    """

    return html_template



def generate_top_tracks_html(top_tracks):
    # Create an HTML template for displaying the top artists
    html_template = """
    <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="shortcut icon" type="image/x-icon" href="https://dishapatel010.github.io/T.png">
    <title>Top Tracks</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f0f0f0;
            margin: 0;
            padding: 0;
        }

        header {
            background-color: #1DB954;
            color: white;
            text-align: center;
            padding: 1rem;
            font-size: 1.5rem;
        }

        main {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            padding: 1rem;
        }

        .track-card {
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 10px;
            margin: 1rem;
            max-width: 300px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            animation: fadeIn 1s ease-in-out;
        }

        .track-image {
            width: 100%;
            max-height: 200px;
            object-fit: cover;
        }

        h2 {
            font-size: 1.5rem;
            margin: 0.5rem;
        }

        p {
            font-size: 1.2rem;
            margin: 0.5rem;
        }

        a {
            text-decoration: none;
            color: #1DB954;
            transition: color 0.2s;
        }

        a:hover {
            color: #0D652D;
        }

        @keyframes fadeIn {
            0% {
                opacity: 0;
            }
            100% {
                opacity: 1;
            }
        }
    </style>
</head>
<body>
    <header>
        <h1>Your Top 5 Tracks</h1>
    </header>
    <main>
    """

    # Add track cards to the HTML template
    for idx, track in enumerate(top_tracks['items'], start=1):
        track_name = track['name']
        artist_names = ', '.join([artist['name'] for artist in track['artists']])
        track_url = track['external_urls']['spotify']
        track_image_url = track['album']['images'][0]['url']
        album_name = track['album']['name']

        html_template += f"""
    <div class="track-card">
        <a href="{track_url}" target="_blank">
            <img class="track-image" src="{track_image_url}" alt="{track_name}">
        </a>
        <h2>{track_name}</h2>
        <p>Artists: {artist_names}</p>
        <p>Album: {album_name}</p>
    </div>
        """

    # Close the HTML template
    html_template += """
        </main>
    </body>
    </html>
    """

    return html_template