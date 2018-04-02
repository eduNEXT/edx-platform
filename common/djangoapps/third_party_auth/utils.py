from random import randint

from django.contrib.auth.models import User


class UsernameGenerator(object):
    """Generates a unique username based on the provided full name."""

    def __init__(self, generator_settings={}):
        default_settings = {
            'SEPARATOR': '_',
            'LOWER': True,
            'RANDOM': False
        }

        self.separator_character = generator_settings.get('SEPARATOR', default_settings['SEPARATOR'])
        self.in_lowercase = generator_settings.get('LOWER', default_settings['LOWER'])
        self.random = generator_settings.get('RANDOM', default_settings['RANDOM'])

    def replace_separator(self, fullname):
        """
        Replaces spaces with a custom separator.
        The default separator character is an underscore.
        """
        username = fullname.replace(' ', self.separator_character)
        return username

    def process_case(self, username):
        """
        If in_lowercase setting is enabled, returns the string downcased,
        otherwise returns the string unmodified.
        """
        if self.in_lowercase:
            return username.lower()
        else:
            return username

    def get_random(self):
        """Returns username a random 4-digit number."""
        random = "%04d" % randint(0, 9999)
        return random

    def generate_username(self, fullname):
        """Utility function which generates a unique username based on the provided string."""
        username = self.replace_separator(fullname)
        initial_username = self.process_case(username)
        user_exists = User.objects.filter(username=initial_username).exists()

        if not user_exists:
            new_username = initial_username

        counter = 1
        while user_exists:
            if self.random:
                suffix = self.get_random()
            else:
                suffix = counter

            new_username = '{}{}{}'.format(initial_username, self.separator_character, suffix)
            user_exists = User.objects.filter(username=new_username).exists()
            counter = counter + 1

        return new_username
