from PyQt6.QtCore import QStandardPaths, QDir, QDateTime


def get_data_path():
    user_movie_path = QStandardPaths.standardLocations(
        QStandardPaths.StandardLocation.MoviesLocation)[0]
    movie_dir = QDir(user_movie_path)
    movie_dir.mkpath('Pat Rec Video Viewer')

    return movie_dir.absoluteFilePath('Pat Rec Video Viewer')


def new_saved_video_name():
    time = QDateTime.currentDateTime()

    return time.toString('yyyy-MM-dd+HH-mm-ss')


def get_saved_video_path(name: str, postfix: str):
    return f'{get_data_path()}/{name}.{postfix}'
