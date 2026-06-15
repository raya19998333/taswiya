# نشر على Render

## الخطوات

### 1. إنشاء حساب GitHub
- اذهب إلى https://github.com
- أنشئ حساب جديد أو سجل الدخول

### 2. إنشاء Repository على GitHub
- انقر `New Repository`
- اسم: `taswiya` (أو أي اسم)
- اختر `Public` أو `Private`
- قم بـ `Create repository`

### 3. رفع الكود إلى GitHub
في Terminal (PowerShell)، قم بتشغيل هذه الأوامر من مجلد المشروع:

```powershell
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/taswiya.git
git push -u origin main
```

استبدل `YOUR_USERNAME` باسم المستخدم GitHub الخاص بك.

### 4. نشر على Render
1. اذهب إلى https://render.com
2. اضغط `Sign up` أو `Sign in`
3. اختر `Connect GitHub`
4. اختر Repository `taswiya`
5. اضغط `Create Web Service`
6. Render سيقرأ `render.yaml` تلقائياً
7. اضغط `Create Service`

### 5. انتظر النشر
- سيستغرق 2-5 دقائق
- ستحصل على رابط مثل: `https://taswiya-xxxxx.onrender.com`

### 6. زيارة التطبيق
- افتح الرابط في المتصفح
- سجل الدخول بـ: `admin / admin123`

---

## ملاحظات مهمة

- البيانات تُحفظ في `taswiya.db` محلياً على الخادم
- عند إعادة تشغيل الخادم، قد تضيع البيانات (استخدم PostgreSQL للإنتاج)
- الـ Free tier يتوقف بعد 15 دقيقة من عدم الاستخدام

---

## إذا واجهت مشاكل

- تحقق من السجلات على لوحة Render
- تأكد أن `requirements.txt` محدّث
- تأكد أن `render.yaml` صحيح
