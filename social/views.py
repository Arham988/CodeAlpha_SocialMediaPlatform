from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from .forms import UserRegistrationForm, LoginForm, ProfileEditForm, PostForm, CommentForm
from .models import Profile, Post, Comment, Like, Follow


def home(request):
    """
    Landing / Feed page view.
    Displays all posts in reverse chronological order (newest first).
    """
    posts = Post.objects.select_related('author', 'author__profile').prefetch_related('likes', 'comments').all()
    liked_post_ids = set()
    if request.user.is_authenticated:
        liked_post_ids = set(Like.objects.filter(user=request.user).values_list('post_id', flat=True))

    context = {
        'posts': posts,
        'liked_post_ids': liked_post_ids,
    }
    return render(request, 'social/home.html', context)


def register_view(request):
    """
    User registration view.
    Validates form, creates user with encrypted password, automatically logs the user in,
    and redirects to their profile.
    """
    if request.user.is_authenticated:
        return redirect('social:profile', username=request.user.username)

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            # Log the user in automatically after registration
            login(request, user)
            messages.success(request, f"Welcome to CodeAlpha Social, @{user.username}!")
            return redirect('social:profile', username=user.username)
    else:
        form = UserRegistrationForm()

    return render(request, 'social/register.html', {'form': form})


def login_view(request):
    """
    User login view using Django's authenticate() and login().
    """
    if request.user.is_authenticated:
        return redirect('social:profile', username=request.user.username)

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, @{user.username}!")
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('social:profile', username=user.username)
            else:
                messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()

    return render(request, 'social/login.html', {'form': form})


def logout_view(request):
    """
    Logs out the user and clears their session.
    """
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('social:home')


def profile_view(request, username):
    """
    Displays the user profile page with bio, stats, followers, following, and the user's posts.
    """
    profile_user = get_object_or_404(User, username=username)
    profile, _ = Profile.objects.get_or_create(user=profile_user)

    is_own_profile = request.user.is_authenticated and request.user == profile_user
    user_posts = profile_user.posts.select_related('author', 'author__profile').prefetch_related('likes', 'comments').all()

    # Dynamic counts from database
    posts_count = user_posts.count()
    followers_count = profile_user.followers.count()
    following_count = profile_user.following.count()

    is_following = False
    if request.user.is_authenticated and not is_own_profile:
        is_following = Follow.objects.filter(follower=request.user, following=profile_user).exists()

    liked_post_ids = set()
    if request.user.is_authenticated:
        liked_post_ids = set(Like.objects.filter(user=request.user).values_list('post_id', flat=True))

    context = {
        'profile_user': profile_user,
        'profile': profile,
        'is_own_profile': is_own_profile,
        'user_posts': user_posts,
        'posts_count': posts_count,
        'followers_count': followers_count,
        'following_count': following_count,
        'is_following': is_following,
        'liked_post_ids': liked_post_ids,
    }
    return render(request, 'social/profile.html', context)


@login_required
def edit_profile(request):
    """
    Allows a logged-in user to edit only their own profile.
    """
    profile = request.user.profile

    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect('social:profile', username=request.user.username)
    else:
        form = ProfileEditForm(instance=profile)

    return render(request, 'social/edit_profile.html', {'form': form})


@login_required
def create_post(request):
    """
    Allows an authenticated user to publish a new post.
    """
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, "Your post has been published!")
            return redirect('social:home')
    else:
        form = PostForm()

    return render(request, 'social/create_post.html', {'form': form})


def post_detail(request, pk):
    """
    Displays the detail view for a specific post along with its comments and like status.
    Allows logged-in users to submit a new comment.
    """
    post = get_object_or_404(Post.objects.select_related('author', 'author__profile').prefetch_related('likes'), pk=pk)
    comments = post.comments.select_related('user', 'user__profile').all()

    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, "You must be logged in to leave a comment.")
            return redirect('social:login')

        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.post = post
            comment.user = request.user
            comment.save()
            messages.success(request, "Your comment has been posted!")
            return redirect('social:post_detail', pk=post.pk)
    else:
        comment_form = CommentForm()

    is_liked = False
    if request.user.is_authenticated:
        is_liked = post.likes.filter(user=request.user).exists()

    context = {
        'post': post,
        'comments': comments,
        'comment_form': comment_form,
        'is_liked': is_liked,
        'is_author': request.user.is_authenticated and request.user == post.author,
    }
    return render(request, 'social/post_detail.html', context)


@login_required
def edit_post(request, pk):
    """
    Allows an authenticated author to edit only their own post.
    Non-authors are strictly denied access.
    """
    post = get_object_or_404(Post, pk=pk)

    # Security check: only the author can edit
    if post.author != request.user:
        raise PermissionDenied("You do not have permission to edit this post.")

    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, "Your post has been updated successfully!")
            return redirect('social:post_detail', pk=post.pk)
    else:
        form = PostForm(instance=post)

    context = {
        'form': form,
        'post': post,
    }
    return render(request, 'social/edit_post.html', context)


@login_required
def delete_post(request, pk):
    """
    Allows an authenticated author to delete only their own post after confirmation.
    Non-authors are strictly denied access.
    """
    post = get_object_or_404(Post, pk=pk)

    # Security check: only the author can delete
    if post.author != request.user:
        raise PermissionDenied("You do not have permission to delete this post.")

    if request.method == 'POST':
        post.delete()
        messages.success(request, "Your post has been deleted successfully.")
        return redirect('social:home')

    context = {
        'post': post,
    }
    return render(request, 'social/delete_post.html', context)


@login_required
def delete_comment(request, pk):
    """
    Allows an authenticated user to delete ONLY their own comment.
    Unauthorized users are strictly blocked.
    """
    comment = get_object_or_404(Comment, pk=pk)
    post_pk = comment.post.pk

    # Security check: only the comment author can delete
    if comment.user != request.user:
        raise PermissionDenied("You do not have permission to delete this comment.")

    if request.method == 'POST' or request.method == 'GET':
        comment.delete()
        messages.success(request, "Comment deleted successfully.")

    return redirect('social:post_detail', pk=post_pk)


@login_required
def toggle_like(request, pk):
    """
    Likes or unlikes a post for the authenticated user.
    Redirects back to the referring page or post detail.
    """
    post = get_object_or_404(Post, pk=pk)
    like = Like.objects.filter(post=post, user=request.user).first()

    if like:
        like.delete()
        messages.info(request, "Post unliked.")
    else:
        Like.objects.create(post=post, user=request.user)
        messages.success(request, "Post liked!")

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('social:post_detail', pk=post.pk)


@login_required
def toggle_follow(request, username):
    """
    Follows or unfollows another user.
    Prevents a user from following themselves.
    """
    target_user = get_object_or_404(User, username=username)

    if request.user == target_user:
        messages.warning(request, "You cannot follow yourself.")
        return redirect('social:profile', username=username)

    follow = Follow.objects.filter(follower=request.user, following=target_user).first()
    if follow:
        follow.delete()
        messages.info(request, f"You have unfollowed @{target_user.username}.")
    else:
        Follow.objects.create(follower=request.user, following=target_user)
        messages.success(request, f"You are now following @{target_user.username}!")

    return redirect('social:profile', username=username)
