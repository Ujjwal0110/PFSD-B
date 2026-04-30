from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.core.cache import cache
import uuid
import random


class CaptchaView(APIView):
    """
    Generates a simple math CAPTCHA to avoid needing third-party API keys.
    Returns: { "captcha_id": "uuid...", "question": "What is 5 + 3?" }
    """
    permission_classes = [AllowAny]

    def get(self, request):
        captcha_type = random.choice(['sequence', 'string', 'logic'])
        captcha_id = str(uuid.uuid4())
        
        if captcha_type == 'sequence':
            start = random.randint(1, 20)
            step = random.randint(2, 5)
            s_type = random.choice(['add', 'sub'])
            
            if s_type == 'add':
                seq = [start + (i * step) for i in range(3)]
                answer = str(seq[-1] + step)
            else:
                start = start + (3 * step) # Ensure positive
                seq = [start - (i * step) for i in range(3)]
                answer = str(seq[-1] - step)
                
            question = f"Next in sequence: {seq[0]}, {seq[1]}, {seq[2]}, ?"
                
        elif captcha_type == 'string':
            import string
            letters = string.ascii_uppercase.replace('O', '').replace('I', '')
            digits = string.digits.replace('0', '').replace('1', '')
            
            # Guarantee at least 2 letters and 2 digits in a 6-char code
            res_list = [random.choice(letters) for _ in range(3)] + [random.choice(digits) for _ in range(3)]
            random.shuffle(res_list)
            res_str = ''.join(res_list)
            
            question = res_str
            answer = res_str.upper()
            
        else: # logic
            l_type = random.choice(['compare', 'multiply'])
            if l_type == 'compare':
                n1 = random.randint(10, 99)
                n2 = random.randint(10, 99)
                while n1 == n2: n2 = random.randint(10, 99)
                is_larger = random.choice([True, False])
                if is_larger:
                    question = f"Which is larger: {n1} or {n2}?"
                    answer = str(max(n1, n2))
                else:
                    question = f"Which is smaller: {n1} or {n2}?"
                    answer = str(min(n1, n2))
            else:
                n1 = random.randint(2, 9)
                n2 = random.randint(2, 5)
                question = f"What is {n1} times {n2}?"
                answer = str(n1 * n2)
            
        # Store answer in cache for 5 minutes (300 seconds)
        cache.set(f"captcha_{captcha_id}", answer, timeout=300)
        
        return Response({
            "captcha_id": captcha_id,
            "question": question,
            "type": captcha_type
        })
