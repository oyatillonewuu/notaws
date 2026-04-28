"""Admin sees all instances. Same operations as users, no owner filter."""
# Per the spec, admins have "Full access" to Instance. The user views are
# already permissive for staff (they bypass the owner filter), so the admin
# surface reuses them directly. This module exists for layout symmetry.
