from django import forms
from django.contrib.auth.models import User
from .models import Profile, Post, Comment


class UserRegistrationForm(forms.ModelForm):
    """
    Form for registering a new user with username, email, and password confirmation.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'Enter your email address', 'class': 'form-input'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter password', 'class': 'form-input'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm your password', 'class': 'form-input'})
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Choose a username', 'class': 'form-input'}),
        }
        help_texts = {
            'username': '',
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("A user with this username already exists.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned_data


class LoginForm(forms.Form):
    """
    Form for user login with username and password.
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Username', 'class': 'form-input'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Password', 'class': 'form-input'})
    )


class ProfileEditForm(forms.ModelForm):
    """
    Form allowing users to edit their own profile bio and profile picture.
    """
    class Meta:
        model = Profile
        fields = ['bio', 'profile_picture']
        widgets = {
            'bio': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Tell everyone something about yourself...',
                'class': 'form-input form-textarea'
            }),
            'profile_picture': forms.FileInput(attrs={'class': 'form-file-input'}),
        }


class PostForm(forms.ModelForm):
    """
    Form for creating and editing posts.
    """
    class Meta:
        model = Post
        fields = ['content', 'image']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': "What's on your mind?",
                'class': 'form-input form-textarea',
            }),
            'image': forms.FileInput(attrs={'class': 'form-file-input'}),
        }
        labels = {
            'content': 'Post Content',
            'image': 'Attach Image (Optional)',
        }


class CommentForm(forms.ModelForm):
    """
    Form for adding a comment to a post.
    """
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Write a comment...',
                'class': 'form-input form-textarea',
            }),
        }
        labels = {
            'content': '',
        }


