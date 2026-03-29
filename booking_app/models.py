from django.db import models

class Category(models.Model):
    
    category_name = models.CharField(max_length=50,null=False, blank=False,unique=True)
    category_image = models.ImageField(upload_to='Categories_images/',null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.category_name
