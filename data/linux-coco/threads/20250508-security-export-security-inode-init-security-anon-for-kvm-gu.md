---
title: '[PATCH RFC v7 3/8] security: Export\n security_inode_init_security_anon for KVM guest_memfd'
date: 2025-05-08
last_reply: 2025-05-08
message_count: 1
participants: ['Shivank Garg']
---

## [1] Shivank Garg — 2025-05-08

On 4/22/2025 10:55 PM, David Hildenbrand wrote:
> On 10.04.25 10:41, Christoph Hellwig wrote:
>> On Tue, Apr 08, 2025 at 11:23:57AM +0000, Shivank Garg wrote:

Here's my understanding of S_PRIVATE flag:
1. S_PRIVATE tells the kernel that an inode is special and it should
skip the LSM permission checks (via IS_PRIVATE()):

​For instance,
int security_inode_mknod(struct inode *dir, struct dentry *dentry,
                         umode_t mode, dev_t dev)
{
        if (unlikely(IS_PRIVATE(dir)))
                return 0;
        return call_int_hook(inode_mknod, dir, dentry, mode, dev);
}

2. In landlock LSM:
S_PRIVATE inodes are denied from opening file and getting path from fd
syscall: open_by_handle_at
calls do_handle_open -> handle_to_path -> get_path_from_fd

static int get_path_from_fd(const s32 fd, struct path *const path)
{
...
        /*
         * Forbids ruleset FDs, internal filesystems (e.g. nsfs), including
         * pseudo filesystems that will never be mountable (e.g. sockfs,
         * pipefs).
         */
        if ((fd_file(f)->f_op == &ruleset_fops) ||
            (fd_file(f)->f_path.mnt->mnt_flags & MNT_INTERNAL) ||
            (fd_file(f)->f_path.dentry->d_sb->s_flags & SB_NOUSER) ||
            d_is_negative(fd_file(f)->f_path.dentry) ||
            IS_PRIVATE(d_backing_inode(fd_file(f)->f_path.dentry)))
                return -EBADFD;

Using is_nouser_or_private() in is_access_to_paths_allowed() (allows accesses
for requests with a common path)

static bool is_access_to_paths_allowed() {
...
        if (is_nouser_or_private(path->dentry))
                return true;

3. S_PRIVATE skips security attribute initialization in SELinux:
security/selinux/hooks.c
sb_finish_set_opts(){
...
                if (inode) {
                        if (!IS_PRIVATE(inode))
                                inode_doinit_with_dentry(inode, NULL);

4. mm/shmem.c
/**
 * shmem_kernel_file_setup - get an unlinked file living in tmpfs which must be
 *      kernel internal.  There will be NO LSM permission checks against the
 *      underlying inode.  So users of this interface must do LSM checks at a
 *      higher layer.  The users are the big_key and shm implementations.  LSM
 *      checks are provided at the key or shm level rather than the inode.
 * @name: name for dentry (to be seen in /proc/<pid>/maps)
 * @size: size to be set for the file
 * @flags: VM_NORESERVE suppresses pre-accounting of the entire object size
 */
struct file *shmem_kernel_file_setup(const char *name, loff_t size, unsigned long flags)
{
        return __shmem_file_setup(shm_mnt, name, size, flags, S_PRIVATE);


From these observations, S_PRIVATE inodes are handled differently from other inodes.
It appears to bypass LSM checks (probably saving some cycles) or In other words, it
ensure the LSMs don't try to reason about these files. While it expects the details
of these inodes should not be leaked to userspace (indicated by comments around
S_PRIVATE refs).

I think we should keep the use of S_PRIVATE flag as it is for secretmem and kvm_gmem.
However, I'm uncertain about whether we still need security_inode_init_security_anon()
for inodes that are already marked S_PRIVATE.
The two seem contradictory. First, we mark an inode as private to bypass LSM checks,
but then initialize security context for it.

I'd appreciate the guidance from the security team.


> From 782a6053268d8a2bddf90ba18c008495b0791710 Mon Sep 17 00:00:00 2001
> From: David Hildenbrand <david@redhat.com>

Thanks for the patch.
I have split this change into two patches and added required documentation.

Best Regards,
Shivank

From 78f48437a88b3b70aa7d80a32db4f269a0804d18 Mon Sep 17 00:00:00 2001
From: David Hildenbrand <david@redhat.com>
Date: Tue, 6 May 2025 09:13:05 +0000
Subject: [PATCH V8 3/9] fs: add alloc_anon_secure_inode() for allocating
 secure anonymous inodes

This introduces alloc_anon_secure_inode() combining alloc_anon_inode()
with security_inode_init_security_anon(), similar to secretmem's usage.

As discussed [1], we need this for cases like secretmem and kvm_gmem
when there might be interest to have global access control via LSMs and
need proper security labeling while maintaining S_PRIVATE.

The new helper avoids duplicating the security initialization for secretmem
and kvm_gmem.

[1]: https://lore.kernel.org/linux-mm/b9e5fa41-62fd-4b3d-bb2d-24ae9d3c33da@redhat.com

Signed-off-by: David Hildenbrand <david@redhat.com>
[Shivank: add documentation]
Signed-off-by: Shivank Garg <shivankg@amd.com>
---
 fs/anon_inodes.c   | 46 ++++++++++++++++++++++++++++++++++++++++------
 include/linux/fs.h |  1 +
 2 files changed, 41 insertions(+), 6 deletions(-)

diff --git a/fs/anon_inodes.c b/fs/anon_inodes.c
index 583ac81669c2..479efcec20bc 100644
--- a/fs/anon_inodes.c
+++ b/fs/anon_inodes.c
@@ -55,17 +55,33 @@ static struct file_system_type anon_inode_fs_type = {
 	.kill_sb	= kill_anon_super,
 };
 
-static struct inode *anon_inode_make_secure_inode(
-	const char *name,
-	const struct inode *context_inode)
+/**
+ * anon_inode_make_secure_inode - allocate an anonymous inode with security context
+ * @sb:		[in]	Superblock to allocate from
+ * @name:	[in]	Name of the class of the newfile (e.g., "secretmem")
+ * @context_inode:
+ *		[in]	Optional parent inode for security inheritance
+ * @fs_internal:
+ *		[in]	If true, keep S_PRIVATE set (flag indicating internal fs inodes)
+ *
+ * The function ensures proper security initialization through the LSM hook
+ * security_inode_init_security_anon().
+ *
+ * Return:	Pointer to new inode on success, ERR_PTR on failure.
+ */
+static struct inode *anon_inode_make_secure_inode(struct super_block *sb,
+		const char *name, const struct inode *context_inode,
+		bool fs_internal)
 {
 	struct inode *inode;
 	int error;
 
-	inode = alloc_anon_inode(anon_inode_mnt->mnt_sb);
+	inode = alloc_anon_inode(sb);
 	if (IS_ERR(inode))
 		return inode;
-	inode->i_flags &= ~S_PRIVATE;
+	if (!fs_internal)
+		inode->i_flags &= ~S_PRIVATE;
+
 	error =	security_inode_init_security_anon(inode, &QSTR(name),
 						  context_inode);
 	if (error) {
@@ -75,6 +91,23 @@ static struct inode *anon_inode_make_secure_inode(
 	return inode;
 }
 
+/**
+ * alloc_anon_secure_inode - allocate a secure anonymous inode
+ * @sb:		[in]	Superblock to allocate the inode from
+ * @name:	[in]	Name of the class of the newfile (e.g., "secretmem")
+ *
+ * Specialized version of anon_inode_make_secure_inode() for filesystem use.
+ * This creates an internal-use inode, marked with S_PRIVATE (hidden from
+ * userspace).
+ *
+ * Return:	A pointer to the new inode on success, ERR_PTR on failure.
+ */
+struct inode *alloc_anon_secure_inode(struct super_block *sb, const char *name)
+{
+	return anon_inode_make_secure_inode(sb, name, NULL, true);
+}
+EXPORT_SYMBOL_GPL(alloc_anon_secure_inode);
+
 static struct file *__anon_inode_getfile(const char *name,
 					 const struct file_operations *fops,
 					 void *priv, int flags,
@@ -88,7 +121,8 @@ static struct file *__anon_inode_getfile(const char *name,
 		return ERR_PTR(-ENOENT);
 
 	if (make_inode) {
-		inode =	anon_inode_make_secure_inode(name, context_inode);
+		inode =	anon_inode_make_secure_inode(anon_inode_mnt->mnt_sb,
+						     name, context_inode, false);
 		if (IS_ERR(inode)) {
 			file = ERR_CAST(inode);
 			goto err;
diff --git a/include/linux/fs.h b/include/linux/fs.h
index 016b0fe1536e..0fded2e3c661 100644
--- a/include/linux/fs.h
+++ b/include/linux/fs.h
@@ -3550,6 +3550,7 @@ extern int simple_write_begin(struct file *file, struct address_space *mapping,
 extern const struct address_space_operations ram_aops;
 extern int always_delete_dentry(const struct dentry *);
 extern struct inode *alloc_anon_inode(struct super_block *);
+extern struct inode *alloc_anon_secure_inode(struct super_block *, const char *);
 extern int simple_nosetlease(struct file *, int, struct file_lease **, void **);
 extern const struct dentry_operations simple_dentry_operations;

---
