import pytest
from app import create_app, db
from models import User, Film, WatchlistEntry
from services.collection_service import FilmNotFoundError
from services.watchlist_service import (
    add_to_watchlist,
    remove_from_watchlist,
    get_watchlist,
    AlreadyInWatchlistError,
    NotInWatchlistError,
)


@pytest.fixture
def app():
    app = create_app(config={
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def sample_user(app):
    with app.app_context():
        user = User(username="watchuser", email="watch@example.com")
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture
def sample_film(app):
    with app.app_context():
        film = Film(title="Inception", year=2010, genre="Sci-Fi")
        db.session.add(film)
        db.session.commit()
        return film.id


def test_add_to_watchlist_nonexistent_film_raises(app, sample_user):
    with app.app_context():
        fake_film_id = 999999

        with pytest.raises(FilmNotFoundError):
            add_to_watchlist(user_id=sample_user, film_id=fake_film_id)


def test_add_to_watchlist_duplicate_raises(app, sample_user, sample_film):
    with app.app_context():
        add_to_watchlist(user_id=sample_user, film_id=sample_film)

        with pytest.raises(AlreadyInWatchlistError):
            add_to_watchlist(user_id=sample_user, film_id=sample_film)

        count = WatchlistEntry.query.filter_by(
            user_id=sample_user, film_id=sample_film
        ).count()
        assert count == 1


def test_remove_from_watchlist_removes_entry(app, sample_user, sample_film):
    with app.app_context():
        add_to_watchlist(user_id=sample_user, film_id=sample_film)

        removed = remove_from_watchlist(user_id=sample_user, film_id=sample_film)

        assert removed is True
        in_db = WatchlistEntry.query.filter_by(
            user_id=sample_user, film_id=sample_film
        ).first()
        assert in_db is None


def test_remove_from_watchlist_missing_entry_raises(app, sample_user, sample_film):
    with app.app_context():
        with pytest.raises(NotInWatchlistError):
            remove_from_watchlist(user_id=sample_user, film_id=sample_film)


def test_add_to_watchlist_honors_public_flag(app, sample_user, sample_film):
    with app.app_context():
        entry = add_to_watchlist(user_id=sample_user, film_id=sample_film, public=False)

        assert entry.public is False


def test_get_watchlist_returns_newest_first(app, sample_user):
    with app.app_context():
        from datetime import datetime, timezone, timedelta

        older_film = Film(title="Amelie", year=2001, genre="Romance")
        newer_film = Film(title="Arrival", year=2016, genre="Sci-Fi")
        db.session.add_all([older_film, newer_film])
        db.session.commit()

        earlier = datetime.now(timezone.utc) - timedelta(days=3)
        later = datetime.now(timezone.utc)

        older_entry = WatchlistEntry(
            user_id=sample_user,
            film_id=older_film.id,
            date_added=earlier,
            public=True,
        )
        newer_entry = WatchlistEntry(
            user_id=sample_user,
            film_id=newer_film.id,
            date_added=later,
            public=True,
        )
        db.session.add_all([older_entry, newer_entry])
        db.session.commit()

        watchlist = get_watchlist(sample_user)
        titles = [film["title"] for film in watchlist]

        assert titles[0] == "Arrival"
        assert titles[1] == "Amelie"
