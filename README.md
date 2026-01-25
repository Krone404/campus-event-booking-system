# campus-event-booking-system

Promotes user to admin (Inside postgress sql query)

SELECT id, email, role FROM users WHERE email='test@admin.com';
UPDATE users SET role='admin' WHERE email='test@admin.com';
SELECT id, email, role FROM users WHERE email='test@admin.com';
