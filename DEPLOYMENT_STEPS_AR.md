# 🚀 تعليمات النشر على Render

## الحالة الحالية ✅
- Git repository تم إنشاؤها محلياً
- جميع الملفات تم commitها
- التطبيق جاهز للنشر

---

## الخطوات المتبقية (3 فقط)

### الخطوة 1️⃣: إنشاء حساب GitHub (إذا لم تكن لديك)
1. اذهب إلى: https://github.com/signup
2. أملأ النموذج
3. تحقق من بريدك الإلكتروني

---

### الخطوة 2️⃣: إنشاء Repository على GitHub
1. اذهب إلى: https://github.com/new
2. اسم الـ Repository: **`taswiya`**
3. الوصف: **"Automated Bank Reconciliation System"**
4. اختر **Public** (أسهل للنشر)
5. اضغط **Create repository**

---

### الخطوة 3️⃣: رفع الكود إلى GitHub
انسخ هذه الأوامر وشغّلها في PowerShell:

```powershell
cd "c:\Users\USER PC\Desktop\Projects\Freelancer\Health\files"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/taswiya.git
git push -u origin main
```

**استبدل `YOUR_USERNAME` باسم المستخدم GitHub الخاص بك**

مثال:
```powershell
git remote add origin https://github.com/ali123/taswiya.git
```

---

### الخطوة 4️⃣: نشر على Render
1. اذهب إلى: https://render.com/auth/signup
2. اضغط **Continue with GitHub**
3. سمح لـ Render بالوصول إلى حسابك
4. اذهب إلى لوحة Render الرئيسية
5. اضغط **New +** في الزاوية العلوية
6. اختر **Web Service**
7. اختر Repository **taswiya**
8. اضغط **Connect**
9. تأكد من الإعدادات:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
10. اضغط **Create Web Service**

---

### الخطوة 5️⃣: انتظر النشر
- سيستغرق 2-5 دقائق
- ستظهر رسالة **"Your service is live"**
- ستحصل على رابط مثل: `https://taswiya-xxxxx.onrender.com`

---

### الخطوة 6️⃣: جرّب التطبيق
افتح الرابط في المتصفح:
- **اسم المستخدم**: `admin`
- **كلمة المرور**: `admin123`

---

## 🎯 النتيجة النهائية
تطبيق مُستضاف وجاهز للعمل 24/7 بدون تكلفة!

---

## ملاحظات مهمة ⚠️

1. **البيانات محلية**: تُحفظ في ملف `taswiya.db` على السيرفر
2. **Free Tier**: قد يتوقف التطبيق بعد 15 دقيقة من عدم الاستخدام
3. **للـ Production**: استخدم PostgreSQL بدل SQLite

---

## إذا حدثت مشاكل

### Error: "remote origin already exists"
```powershell
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/taswiya.git
```

### Error: "authentication failed"
تأكد أن:
- اسم المستخدم صحيح
- كلمة المرور صحيحة (أو استخدم Personal Access Token)

### التطبيق لا يعمل على Render
- اذهب إلى **Logs** في لوحة Render
- ابحث عن رسالة الخطأ

---

استفسر إذا احتجت مساعدة في أي خطوة! 💪
