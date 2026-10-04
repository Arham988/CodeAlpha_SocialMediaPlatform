from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.contrib import admin
from social.models import Profile, Post, Comment, Like, Follow
import io
from PIL import Image


class AuthenticationAndProfileTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpassword123'
        )

    def test_profile_automatically_created_on_user_creation(self):
        """Test that a Profile is automatically created via signal when User is created."""
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertEqual(Profile.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self.user.profile.user, self.user)

    def test_user_registration_success(self):
        """Test successful registration: user created, profile created, auto-logged in, redirected."""
        response = self.client.post(reverse('social:register'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'strongpassword123',
            'confirm_password': 'strongpassword123'
        }, follow=True)

        # User and profile exist in database
        self.assertTrue(User.objects.filter(username='newuser').exists())
        new_user = User.objects.get(username='newuser')
        self.assertTrue(Profile.objects.filter(user=new_user).exists())

        # Auto-login verified
        self.assertEqual(int(self.client.session['_auth_user_id']), new_user.id)
        # Redirected to profile page
        self.assertContains(response, '@newuser')

    def test_registration_password_mismatch(self):
        """Test registration fails when password and confirm_password do not match."""
        response = self.client.post(reverse('social:register'), {
            'username': 'mismatchuser',
            'email': 'mismatch@example.com',
            'password': 'password123',
            'confirm_password': 'differentpassword'
        })
        self.assertFalse(User.objects.filter(username='mismatchuser').exists())
        self.assertFormError(response.context['form'], 'confirm_password', 'Passwords do not match.')

    def test_registration_duplicate_username(self):
        """Test registration fails when username already exists."""
        response = self.client.post(reverse('social:register'), {
            'username': 'testuser',  # already exists
            'email': 'different@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        self.assertFormError(response.context['form'], 'username', 'A user with this username already exists.')

    def test_user_login_success(self):
        """Test valid credentials log the user in and redirect to profile."""
        response = self.client.post(reverse('social:login'), {
            'username': 'testuser',
            'password': 'testpassword123'
        }, follow=True)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.id)
        self.assertContains(response, '@testuser')

    def test_user_login_invalid_credentials(self):
        """Test invalid credentials show error message and do not log in."""
        response = self.client.post(reverse('social:login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(response, 'Invalid username or password.')

    def test_user_logout(self):
        """Test logging out clears session and redirects to home."""
        self.client.login(username='testuser', password='testpassword123')
        self.assertIn('_auth_user_id', self.client.session)

        response = self.client.get(reverse('social:logout'), follow=True)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(response, 'You have been logged out successfully.')

    def test_profile_page_display(self):
        """Test profile page displays username, bio, and stat counters."""
        self.user.profile.bio = "Hello! This is my test bio."
        self.user.profile.save()

        response = self.client.get(reverse('social:profile', kwargs={'username': 'testuser'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '@testuser')
        self.assertContains(response, 'Hello! This is my test bio.')
        self.assertContains(response, '0')  # posts/followers/following counts

    def test_edit_profile_requires_login(self):
        """Test unauthenticated user cannot access edit profile view."""
        response = self.client.get(reverse('social:edit_profile'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_edit_profile_updates_bio_and_picture(self):
        """Test logged-in user can update their bio and upload profile picture."""
        self.client.login(username='testuser', password='testpassword123')

        # Create a small valid test image in memory
        image_io = io.BytesIO()
        image = Image.new('RGB', (100, 100), color='blue')
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        test_file = SimpleUploadedFile("avatar.jpg", image_io.read(), content_type="image/jpeg")

        response = self.client.post(reverse('social:edit_profile'), {
            'bio': 'Updated bio description.',
            'profile_picture': test_file
        }, follow=True)

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.bio, 'Updated bio description.')
        self.assertTrue(bool(self.user.profile.profile_picture))
        self.assertContains(response, 'Updated bio description.')

    def test_user_cannot_edit_other_user_profile(self):
        """Verify that edit_profile strictly targets request.user.profile, never another user's profile."""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpassword'
        )
        other_user.profile.bio = "Original other bio"
        other_user.profile.save()

        # Login as testuser and submit edit form
        self.client.login(username='testuser', password='testpassword123')
        self.client.post(reverse('social:edit_profile'), {
            'bio': 'Testuser new bio'
        })

        # other_user's profile MUST be untouched
        other_user.profile.refresh_from_db()
        self.assertEqual(other_user.profile.bio, "Original other bio")
        # testuser's profile was updated
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.bio, "Testuser new bio")

    def test_navbar_changes_based_on_authentication(self):
        """Test navbar shows Login/Register when logged out, and Create Post/My Profile/Logout when logged in."""
        # 1. Logged out
        response = self.client.get(reverse('social:home'))
        self.assertContains(response, 'Login')
        self.assertContains(response, 'Register')
        self.assertNotContains(response, 'Create Post')
        self.assertNotContains(response, 'My Profile')
        self.assertNotContains(response, 'Logout')

        # 2. Logged in
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(reverse('social:home'))
        self.assertContains(response, 'Create Post')
        self.assertContains(response, 'My Profile')
        self.assertContains(response, 'Logout')
        self.assertNotContains(response, 'Register')


class PostSystemTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='author1',
            email='author1@example.com',
            password='password123'
        )
        self.user2 = User.objects.create_user(
            username='author2',
            email='author2@example.com',
            password='password123'
        )
        self.post1 = Post.objects.create(
            author=self.user1,
            content="Hello from Author 1! First post."
        )

    def test_logged_out_user_can_view_posts_on_home_feed(self):
        """Test that unauthenticated users can view posts on the feed."""
        response = self.client.get(reverse('social:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hello from Author 1! First post.")
        self.assertContains(response, "@author1")

    def test_logged_in_user_can_create_post(self):
        """Test authenticated user can create a text post."""
        self.client.login(username='author1', password='password123')
        response = self.client.post(reverse('social:create_post'), {
            'content': 'This is a brand new post by author 1.'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Post.objects.filter(content='This is a brand new post by author 1.').exists())
        new_post = Post.objects.get(content='This is a brand new post by author 1.')
        self.assertEqual(new_post.author, self.user1)
        self.assertContains(response, 'This is a brand new post by author 1.')

    def test_create_post_requires_login(self):
        """Test unauthenticated user is redirected to login when accessing create post."""
        response = self.client.get(reverse('social:create_post'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_image_upload_with_post(self):
        """Test creating a post with an attached image."""
        self.client.login(username='author1', password='password123')

        # Create valid test image
        image_io = io.BytesIO()
        image = Image.new('RGB', (120, 120), color='green')
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        test_file = SimpleUploadedFile("post_pic.jpg", image_io.read(), content_type="image/jpeg")

        response = self.client.post(reverse('social:create_post'), {
            'content': 'Post with image attachment!',
            'image': test_file
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        post = Post.objects.get(content='Post with image attachment!')
        self.assertTrue(bool(post.image))
        self.assertContains(response, 'Post with image attachment!')

    def test_user_can_edit_own_post(self):
        """Test author can edit their own post."""
        self.client.login(username='author1', password='password123')
        response = self.client.post(reverse('social:edit_post', kwargs={'pk': self.post1.pk}), {
            'content': 'Updated content for post 1.'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.post1.refresh_from_db()
        self.assertEqual(self.post1.content, 'Updated content for post 1.')
        self.assertContains(response, 'Updated content for post 1.')

    def test_user_cannot_edit_another_user_post(self):
        """Test user cannot edit another user's post (raises PermissionDenied / 403)."""
        # Log in as user2 and attempt to edit user1's post
        self.client.login(username='author2', password='password123')
        response = self.client.post(reverse('social:edit_post', kwargs={'pk': self.post1.pk}), {
            'content': 'Malicious attempt to change post.'
        })
        self.assertEqual(response.status_code, 403)
        self.post1.refresh_from_db()
        self.assertEqual(self.post1.content, "Hello from Author 1! First post.")

    def test_user_can_delete_own_post(self):
        """Test author can delete their own post after confirmation."""
        self.client.login(username='author1', password='password123')
        # Confirm page loads
        confirm_res = self.client.get(reverse('social:delete_post', kwargs={'pk': self.post1.pk}))
        self.assertEqual(confirm_res.status_code, 200)
        self.assertContains(confirm_res, 'Confirm Deletion')

        # POST delete
        response = self.client.post(reverse('social:delete_post', kwargs={'pk': self.post1.pk}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Post.objects.filter(pk=self.post1.pk).exists())
        self.assertContains(response, 'Your post has been deleted successfully.')

    def test_user_cannot_delete_another_user_post(self):
        """Test user cannot delete another user's post (raises PermissionDenied / 403)."""
        # Log in as user2 and attempt to delete user1's post
        self.client.login(username='author2', password='password123')
        response = self.client.post(reverse('social:delete_post', kwargs={'pk': self.post1.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Post.objects.filter(pk=self.post1.pk).exists())

    def test_post_detail_view(self):
        """Test post detail page displays post content, author, and timestamp."""
        response = self.client.get(reverse('social:post_detail', kwargs={'pk': self.post1.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.post1.content)
        self.assertContains(response, '@author1')

    def test_posts_display_on_user_profile(self):
        """Test that user's posts display on their profile page with updated post count."""
        response = self.client.get(reverse('social:profile', kwargs={'username': 'author1'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.post1.content)
        self.assertContains(response, 'Posts (1)')


class CommentSystemTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='password123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='password123'
        )
        self.post = Post.objects.create(
            author=self.user1,
            content='Testing comments feature on this post.'
        )
        self.comment1 = Comment.objects.create(
            post=self.post,
            user=self.user1,
            content='This is a first comment by user1.'
        )

    def test_logged_out_user_can_view_comments(self):
        """Test that unauthenticated user can view comments on the post detail page."""
        response = self.client.get(reverse('social:post_detail', kwargs={'pk': self.post.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This is a first comment by user1.')
        self.assertContains(response, '@user1')
        self.assertContains(response, 'Comments (1)')
        # Should prompt to log in to leave a comment
        self.assertContains(response, 'Log in')

    def test_logged_in_user_can_add_comment(self):
        """Test that logged-in user can submit a comment and it appears immediately."""
        self.client.login(username='user2', password='password123')
        response = self.client.post(reverse('social:post_detail', kwargs={'pk': self.post.pk}), {
            'content': 'Insightful post! Here is my comment.'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Comment.objects.filter(content='Insightful post! Here is my comment.').exists())
        new_comment = Comment.objects.get(content='Insightful post! Here is my comment.')
        self.assertEqual(new_comment.user, self.user2)
        self.assertEqual(new_comment.post, self.post)

        # Assert content, username, and updated count appear immediately
        self.assertContains(response, 'Insightful post! Here is my comment.')
        self.assertContains(response, '@user2')
        self.assertContains(response, 'Comments (2)')
        self.assertContains(response, 'Your comment has been posted!')

    def test_logged_out_user_cannot_submit_comment(self):
        """Test unauthenticated user submitting comment is redirected to login."""
        response = self.client.post(reverse('social:post_detail', kwargs={'pk': self.post.pk}), {
            'content': 'Attempt to comment while logged out.'
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
        self.assertFalse(Comment.objects.filter(content='Attempt to comment while logged out.').exists())

    def test_user_can_delete_own_comment(self):
        """Test that a user can delete their own comment."""
        self.client.login(username='user1', password='password123')
        response = self.client.post(reverse('social:delete_comment', kwargs={'pk': self.comment1.pk}), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Comment.objects.filter(pk=self.comment1.pk).exists())
        self.assertContains(response, 'Comment deleted successfully.')
        self.assertContains(response, 'Comments (0)')

    def test_user_cannot_delete_another_user_comment(self):
        """Test that a user cannot delete another user's comment (raises PermissionDenied / 403)."""
        # User 2 logs in and attempts to delete User 1's comment
        self.client.login(username='user2', password='password123')
        response = self.client.post(reverse('social:delete_comment', kwargs={'pk': self.comment1.pk}))

        self.assertEqual(response.status_code, 403)
        # Comment must still exist in the database
        self.assertTrue(Comment.objects.filter(pk=self.comment1.pk).exists())


class LikeAndFollowSystemTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.userA = User.objects.create_user(
            username='userA',
            email='userA@example.com',
            password='password123'
        )
        self.userB = User.objects.create_user(
            username='userB',
            email='userB@example.com',
            password='password123'
        )
        self.post = Post.objects.create(
            author=self.userB,
            content='A post by User B waiting for likes.'
        )

    def test_user_a_likes_post_and_count_increases(self):
        """Test User A likes a post, like count increases, and UI shows Unlike."""
        self.client.login(username='userA', password='password123')
        response = self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Like.objects.filter(post=self.post, user=self.userA).exists())
        self.assertEqual(self.post.likes.count(), 1)
        self.assertContains(response, 'Unlike')
        self.assertContains(response, 'Post liked!')

    def test_user_a_unlikes_post_and_count_decreases(self):
        """Test User A unlikes a post, like count decreases, and UI shows Like."""
        Like.objects.create(post=self.post, user=self.userA)
        self.assertEqual(self.post.likes.count(), 1)

        self.client.login(username='userA', password='password123')
        response = self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Like.objects.filter(post=self.post, user=self.userA).exists())
        self.assertEqual(self.post.likes.count(), 0)
        self.assertContains(response, 'Like')
        self.assertContains(response, 'Post unliked.')

    def test_duplicate_likes_prevented_by_database_constraint(self):
        """Test database uniqueness constraint prevents duplicate likes."""
        Like.objects.create(post=self.post, user=self.userA)
        with self.assertRaises(IntegrityError):
            Like.objects.create(post=self.post, user=self.userA)

    def test_user_a_follows_user_b_and_counts_increase(self):
        """Test User A follows User B, follower/following counts increase, and Unfollow button appears."""
        self.client.login(username='userA', password='password123')
        response = self.client.post(reverse('social:toggle_follow', kwargs={'username': 'userB'}), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Follow.objects.filter(follower=self.userA, following=self.userB).exists())

        # Check User B's follower count
        self.assertEqual(self.userB.followers.count(), 1)
        # Check User A's following count
        self.assertEqual(self.userA.following.count(), 1)

        # Profile of User B shows 1 follower and Unfollow button
        profile_b_res = self.client.get(reverse('social:profile', kwargs={'username': 'userB'}))
        self.assertContains(profile_b_res, 'Followers')
        self.assertContains(profile_b_res, '1')
        self.assertContains(profile_b_res, 'Unfollow')

    def test_user_a_unfollows_user_b_and_counts_decrease(self):
        """Test User A unfollows User B and counts decrease."""
        Follow.objects.create(follower=self.userA, following=self.userB)
        self.assertEqual(self.userB.followers.count(), 1)
        self.assertEqual(self.userA.following.count(), 1)

        self.client.login(username='userA', password='password123')
        response = self.client.post(reverse('social:toggle_follow', kwargs={'username': 'userB'}), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Follow.objects.filter(follower=self.userA, following=self.userB).exists())
        self.assertEqual(self.userB.followers.count(), 0)
        self.assertEqual(self.userA.following.count(), 0)
        self.assertContains(response, 'Follow')
        self.assertContains(response, 'You have unfollowed @userB.')

    def test_user_cannot_follow_themselves(self):
        """Test that a user cannot follow themselves."""
        self.client.login(username='userA', password='password123')
        response = self.client.post(reverse('social:toggle_follow', kwargs={'username': 'userA'}), follow=True)

        self.assertFalse(Follow.objects.filter(follower=self.userA, following=self.userA).exists())
        self.assertContains(response, 'You cannot follow yourself.')

        # Model level validation check
        follow = Follow(follower=self.userA, following=self.userA)
        with self.assertRaises(ValidationError):
            follow.save()

    def test_duplicate_follows_prevented_by_constraint(self):
        """Test database uniqueness constraint prevents duplicate follows."""
        Follow.objects.create(follower=self.userA, following=self.userB)
        with self.assertRaises(IntegrityError):
            Follow.objects.create(follower=self.userA, following=self.userB)

    def test_logged_out_users_cannot_like_or_follow(self):
        """Test unauthenticated users cannot like or follow and are redirected to login."""
        # Attempt like
        like_res = self.client.post(reverse('social:toggle_like', kwargs={'pk': self.post.pk}))
        self.assertEqual(like_res.status_code, 302)
        self.assertIn('/login/', like_res.url)
        self.assertFalse(Like.objects.filter(post=self.post).exists())

        # Attempt follow
        follow_res = self.client.post(reverse('social:toggle_follow', kwargs={'username': 'userB'}))
        self.assertEqual(follow_res.status_code, 302)
        self.assertIn('/login/', follow_res.url)
        self.assertFalse(Follow.objects.filter(following=self.userB).exists())

    def test_admin_models_registered(self):
        """Test that Profile, Post, Comment, Like, and Follow models are all registered in admin."""
        self.assertTrue(admin.site.is_registered(Profile))
        self.assertTrue(admin.site.is_registered(Post))
        self.assertTrue(admin.site.is_registered(Comment))
        self.assertTrue(admin.site.is_registered(Like))
        self.assertTrue(admin.site.is_registered(Follow))



