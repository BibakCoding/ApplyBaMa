/* ---------------------------------------------------------------------------
   ApplyBaMa - pages/chat.js
   The dashboard's chat page.

   The fragment (dashboard/fragments/chat.html) is a shell; this script fills
   it: it fetches the conversation list (chat/data/), opens threads
   (chat/thread/<id>/), and performs every action through the HTTP endpoints
   (send, edit, delete, pin, forward, read, upload). Realtime updates arrive
   on the chat socket opened by realtime.js and are re-dispatched here as
   document CustomEvents (ab:chat-*), so this file never touches WebSocket
   internals.

   Security model, mirrored from the server: there is no user directory and
   no way to pick an arbitrary recipient — threads are only ever opened from
   the server-rendered conversation list. Server text is inserted with
   textContent everywhere; no innerHTML path for user content.
--------------------------------------------------------------------------- */
/* The dashboard injects the fragment with innerHTML long after this file has
   run, so the element handles are re-captured on every injection by
   initChatScripts() (dashboard.js calls it right after the injection, the way
   it calls initProfileScripts()). `els` is mutated rather than rebuilt so the
   handlers defined below always see the elements of the current fragment. */
(function () {
    "use strict";

    // Detail routes are published with the id placeholder dropped, i.e.
    // "/dashboard/chat/thread/"; detailUrl() joins ids onto them exactly once.
    var urls = {};
    var els = {};
    var delegatesBound = false;

    function captureElements() {
        els.list = document.getElementById("abChatList");
        els.items = document.getElementById("abChatItems");
        els.hint = document.getElementById("abChatListHint");
        els.thread = document.getElementById("abChatThread");
        els.back = document.getElementById("abChatBack");
        els.peerName = document.getElementById("abChatPeerName");
        els.peerStatus = document.getElementById("abChatPeerStatus");
        els.peerAvatar = document.getElementById("abChatPeerAvatar");
        els.typing = document.getElementById("abChatTyping");
        els.pinned = document.getElementById("abChatPinned");
        els.pinnedBody = document.getElementById("abChatPinnedBody");
        els.messages = document.getElementById("abChatMessages");
        els.replyBox = document.getElementById("abChatReplyBox");
        els.replyPreview = document.getElementById("abChatReplyPreview");
        els.replyCancel = document.getElementById("abChatReplyCancel");
        els.input = document.getElementById("abChatInput");
        els.send = document.getElementById("abChatSend");
        els.attach = document.getElementById("abChatAttach");
        els.file = document.getElementById("abChatFile");
        els.fileHint = document.getElementById("abChatFileHint");
    }

    var state = {
        conversations: [],
        contacts: [],           // allowed partners with no thread yet
        canFile: null,          // the viewer's own upload allowance (MB)
        activeId: null,
        thread: null,           // last fetched thread JSON
        replyTo: null,          // message id being replied to
        pendingAttachments: [], // File objects waiting to be uploaded after send
        sending: false,
        typingTimer: null,
        typingSentAt: 0,
        peerReadAt: null,       // when the peer last opened this thread
    };

    function t(key, fallback) {
        var i18n = window.I18N || {};
        return i18n[key] || fallback;
    }

    function toast(message, type) {
        if (typeof window.notify === "function") window.notify(message, type);
    }

    // Timestamps arrive as ISO strings; the browser's own locale decides how
    // they read, so no format string is translated here.
    function formatTime(value) {
        if (!value) return "";
        var date = new Date(value);
        if (isNaN(date.getTime())) return "";
        return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    function getCsrf() {
        return window.ApplyBaMa && window.ApplyBaMa.getCsrfToken
            ? window.ApplyBaMa.getCsrfToken()
            : "";
    }

    function request(url, options) {
        return fetch(url, options).then(function (r) {
            // An expired session answers JSON 401 (core.middleware.ajax_auth)
            // instead of the HTML login page; hand the visitor to the login
            // form rather than letting the fragment fail to load.
            if (r.status === 401 && window.ApplyBaMa) {
                window.ApplyBaMa.handleAuthExpired();
            }
            return r.json().then(function (data) {
                if (!r.ok) throw data;
                return data;
            });
        });
    }

    function post(url, body) {
        return request(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrf(),
                "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify(body || {}),
        });
    }

    /* ------------------------------------------------------------------
       Conversation list
    ------------------------------------------------------------------ */

    function loadConversations() {
        return request(urls.chatConversations, {
            headers: { "X-Requested-With": "XMLHttpRequest" },
        }).then(function (data) {
            state.conversations = data.conversations || [];
            state.contacts = data.contacts || [];
            state.canFile = data.can_file == null ? null : data.can_file;
            renderList();
            updateSidebarBadge();
        });
    }

    function renderList() {
        els.items.innerHTML = "";
        els.hint.textContent = "";

        if (!state.conversations.length && !state.contacts.length) {
            var empty = document.createElement("div");
            empty.className = "ab-chat__empty";
            var icon = document.createElement("i");
            icon.className = "fas fa-comments ab-chat__empty-icon";
            var p = document.createElement("p");
            p.textContent = t("chatNoConversations", "No conversations yet.");
            var sub = document.createElement("p");
            sub.className = "ab-chat__empty-sub";
            sub.textContent = t(
                "chatNoConversationsSub",
                "You can always message Support here; students an agent or company adds appear automatically."
            );
            empty.appendChild(icon);
            empty.appendChild(p);
            empty.appendChild(sub);
            els.items.appendChild(empty);
            return;
        }

        state.conversations.forEach(function (c) {
            var row = document.createElement("div");
            row.className = "ab-chat__item" + (c.unread ? " ab-chat__item--unread" : "");
            row.setAttribute("role", "listitem");
            row.setAttribute("tabindex", "0");
            row.dataset.id = c.id;

            var avatar = document.createElement("span");
            avatar.className = "ab-chat__avatar" + (c.peer.online ? " ab-chat__avatar--online" : "");
            var avatarIcon = document.createElement("i");
            avatarIcon.className = "fas fa-user";
            avatar.appendChild(avatarIcon);

            var main = document.createElement("span");
            main.className = "ab-chat__item-main";

            var nameRow = document.createElement("span");
            nameRow.className = "ab-chat__item-name";
            nameRow.textContent = c.peer.name;
            if (c.peer.is_staff) {
                var tag = document.createElement("span");
                tag.className = "ab-chat__staff-tag";
                tag.textContent = t("chatSupportTag", "Support");
                nameRow.appendChild(tag);
            }
            var last = document.createElement("span");
            last.className = "ab-chat__item-last";
            last.textContent = c.last_message || t("chatNoMessages", "No messages yet");
            main.appendChild(nameRow);
            main.appendChild(last);

            var meta = document.createElement("span");
            meta.className = "ab-chat__item-meta";
            var time = document.createElement("span");
            time.className = "ab-chat__item-time";
            time.textContent = formatTime(c.last_message_at);
            meta.appendChild(time);
            if (c.unread) {
                var badge = document.createElement("span");
                badge.className = "ab-chat__unread";
                badge.textContent = c.unread > 99 ? "99+" : String(c.unread);
                meta.appendChild(badge);
            }

            row.appendChild(avatar);
            row.appendChild(main);
            row.appendChild(meta);
            row.addEventListener("click", function () {
                openThread(c.id);
            });
            row.addEventListener("keydown", function (e) {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    openThread(c.id);
                }
            });
            els.items.appendChild(row);
        });

        // The framework's other allowed pairs, before a first message exists.
        // Rows come from the server's ownership-derived list, never a search.
        if (state.contacts.length) {
            var heading = document.createElement("div");
            heading.className = "ab-chat__section";
            heading.textContent = t("chatStartConversation", "Start a conversation");
            els.items.appendChild(heading);
            state.contacts.forEach(function (contact) {
                els.items.appendChild(renderContactRow(contact));
            });
        }
    }

    function renderContactRow(contact) {
        var row = document.createElement("div");
        row.className = "ab-chat__item ab-chat__item--contact";
        row.setAttribute("role", "listitem");
        row.setAttribute("tabindex", "0");
        row.dataset.peerId = contact.id;

        var avatar = document.createElement("span");
        avatar.className = "ab-chat__avatar";
        var avatarIcon = document.createElement("i");
        avatarIcon.className = contact.is_staff ? "fas fa-headset" : "fas fa-user";
        avatar.appendChild(avatarIcon);

        var main = document.createElement("span");
        main.className = "ab-chat__item-main";
        var nameRow = document.createElement("span");
        nameRow.className = "ab-chat__item-name";
        nameRow.textContent = contact.name;
        var label = document.createElement("span");
        label.className = "ab-chat__contact-label";
        label.textContent = contact.label || "";
        main.appendChild(nameRow);
        main.appendChild(label);

        var go = document.createElement("span");
        go.className = "ab-chat__contact-go";
        var goIcon = document.createElement("i");
        goIcon.className = "fas fa-comment-dots";
        go.appendChild(goIcon);

        row.appendChild(avatar);
        row.appendChild(main);
        row.appendChild(go);
        row.addEventListener("click", function () {
            openContactThread(contact);
        });
        row.addEventListener("keydown", function (e) {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                openContactThread(contact);
            }
        });
        return row;
    }

    function updateSidebarBadge() {
        var badge = document.getElementById("chatBadge");
        if (!badge) return;
        var total = state.conversations.reduce(function (sum, c) {
            return sum + (c.unread || 0);
        }, 0);
        if (total > 0) {
            badge.textContent = total > 99 ? "99+" : String(total);
            badge.classList.remove("hidden");
        } else {
            badge.classList.add("hidden");
        }
    }

    /* ------------------------------------------------------------------
       Thread
    ------------------------------------------------------------------ */

    function detailUrl(base, id) {
        return base.endsWith("/") ? base + id + "/" : base + "/" + id + "/";
    }

    function openThread(id) {
        request(detailUrl(urls.chatThread, id), {
            headers: { "X-Requested-With": "XMLHttpRequest" },
        })
            .then(function (data) {
                state.activeId = id;
                state.thread = data.thread;
                state.replyTo = null;
                state.peerReadAt = data.thread.peer_last_read_at || null;
                renderThread();
                // Tell the server this thread is now read; the socket pushes
                // the receipt to both sides and the list badge drops.
                sendRead();
                if (window.history && window.history.replaceState) {
                    var url = new URL(window.location.href);
                    url.searchParams.set("chat", id);
                    window.history.replaceState({ page: "chat" }, "", url);
                }
            })
            .catch(function (err) {
                toast((err && err.message) || t("chatLoadError", "Could not open the conversation."), "error");
            });
    }

    function openContactThread(contact) {
        // A contact has no conversation row yet — it is created on the first
        // send (the send endpoint pairs the two users itself). Until then the
        // thread is rendered from the contact alone.
        state.activeId = null;
        state.replyTo = null;
        state.thread = {
            id: null,
            peer: {
                id: contact.id,
                name: contact.name,
                username: "",
                is_staff: !!contact.is_staff,
                online: false,
            },
            messages: [],
            pinned: null,
            my_last_read_at: null,
            peer_last_read_at: null,
            can_file: state.canFile,
        };
        state.peerReadAt = null;
        renderThread();
        if (window.history && window.history.replaceState) {
            var url = new URL(window.location.href);
            url.searchParams.delete("chat");
            window.history.replaceState({ page: "chat" }, "", url);
        }
    }

    function closeThread() {
        state.activeId = null;
        state.thread = null;
        state.replyTo = null;
        state.pendingAttachments = [];
        els.thread.hidden = true;
        els.list.hidden = false;
        renderList();
        updateSidebarBadge();
    }

    function renderThread() {
        var th = state.thread;
        if (!th) return;
        els.list.hidden = true;
        els.thread.hidden = false;

        els.peerName.textContent = th.peer.name;
        setPeerStatus(th.peer.online);
        els.typing.hidden = true;

        renderPinned(th.pinned);
        renderFileHint();

        els.messages.innerHTML = "";
        (th.messages || []).forEach(function (m) {
            els.messages.appendChild(renderMessage(m));
        });
        scrollMessagesToBottom();

        // The thread URL param lets a refresh reopen the same conversation.
    }

    function setPeerStatus(online) {
        els.peerStatus.textContent = online
            ? t("chatOnline", "online")
            : t("chatOffline", "offline");
        els.peerAvatar.classList.toggle("ab-chat__avatar--online", !!online);
    }

    function renderPinned(pinned) {
        if (!pinned) {
            els.pinned.hidden = true;
            return;
        }
        els.pinned.hidden = false;
        els.pinnedBody.textContent = pinned.body || t("chatDeletedMessage", "Message deleted");
    }

    function renderFileHint() {
        var allowance = state.thread && state.thread.can_file;
        if (allowance == null) {
            els.fileHint.textContent = t(
                "chatFileNotAllowed",
                "File sending is not enabled for your account. Ask the support team."
            );
            els.attach.disabled = true;
            els.attach.classList.add("ab-chat__attach--disabled");
        } else {
            els.fileHint.textContent = t("chatFileLimit", "Files up to __MB MB").replace("__MB", String(allowance));
            els.attach.disabled = false;
            els.attach.classList.remove("ab-chat__attach--disabled");
        }
    }

    /* ------------------------------------------------------------------
       Messages
    ------------------------------------------------------------------ */

    function renderMessage(m) {
        var row = document.createElement("div");
        row.className = "ab-chat__msg" + (m.mine ? " ab-chat__msg--mine" : "");
        row.dataset.id = m.id;

        if (m.forwarded) {
            var fwd = document.createElement("div");
            fwd.className = "ab-chat__msg-forwarded";
            fwd.textContent = t("chatForwarded", "Forwarded");
            row.appendChild(fwd);
        }

        if (m.reply_preview) {
            var quote = document.createElement("div");
            quote.className = "ab-chat__msg-quote";
            quote.textContent = m.reply_preview.deleted
                ? t("chatDeletedMessage", "Message deleted")
                : m.reply_preview.body || (m.reply_preview.has_file ? t("chatAttachment", "📎 Attachment") : "");
            row.appendChild(quote);
        }

        if (m.is_deleted) {
            var gone = document.createElement("div");
            gone.className = "ab-chat__msg-deleted";
            gone.textContent = t("chatDeletedMessage", "Message deleted");
            row.appendChild(gone);
            return row;
        }

        (m.attachments || []).forEach(function (a) {
            row.appendChild(renderAttachment(a));
        });

        if (m.body) {
            var text = document.createElement("div");
            text.className = "ab-chat__msg-body";
            text.textContent = m.body;
            row.appendChild(text);
        }

        var foot = document.createElement("div");
        foot.className = "ab-chat__msg-foot";
        var time = document.createElement("span");
        time.className = "ab-chat__msg-time";
        time.textContent = formatTime(m.created_at);
        foot.appendChild(time);
        if (m.is_edited) {
            var edited = document.createElement("span");
            edited.className = "ab-chat__msg-edited";
            edited.textContent = t("chatEdited", "(edited)");
            foot.appendChild(edited);
        }
        // My messages show the read state: one tick (sent) or two (read).
        if (m.mine) {
            var ticks = document.createElement("i");
            ticks.className = m.read
                ? "fas fa-check-double ab-chat__tick ab-chat__tick--read"
                : "fas fa-check ab-chat__tick";
            ticks.title = m.read ? t("chatRead", "Read") : t("chatSent", "Sent");
            foot.appendChild(ticks);
            // ...and how late the peer read it. The time above the ticks is the
            // send time, so both ends of the story are on screen.
            if (m.read && state.peerReadAt) {
                var readAt = document.createElement("span");
                readAt.className = "ab-chat__msg-readat";
                readAt.textContent = formatTime(state.peerReadAt);
                readAt.title = t("chatRead", "Read") + " " + formatTime(state.peerReadAt);
                foot.appendChild(readAt);
            }
        }
        row.appendChild(foot);

        // Action menu: reply is universal; edit/pin/delete are sender-only;
        // forward is offered on any visible message. (Server re-checks all.)
        if (!m.is_deleted) {
            var menu = buildMessageMenu(m);
            row.appendChild(menu);
        }
        return row;
    }

    function renderAttachment(a) {
        var wrap = document.createElement("div");
        wrap.className = "ab-chat__attachment";
        var link = document.createElement("a");
        link.href = a.url;
        link.target = "_blank";
        link.rel = "noopener";
        if (a.is_image) {
            var img = document.createElement("img");
            img.src = a.url;
            img.alt = a.name;
            img.className = "ab-chat__attachment-image";
            img.loading = "lazy";
            link.appendChild(img);
        } else {
            var chip = document.createElement("span");
            chip.className = "ab-chat__attachment-chip";
            var icon = document.createElement("i");
            icon.className = "fas fa-file-pdf";
            var name = document.createElement("span");
            name.textContent = a.name;
            chip.appendChild(icon);
            chip.appendChild(name);
            link.appendChild(chip);
        }
        wrap.appendChild(link);
        return wrap;
    }

    function buildMessageMenu(m) {
        var menu = document.createElement("div");
        menu.className = "ab-chat__msg-menu";

        var replyBtn = iconButton("fas fa-reply", t("chatReply", "Reply"));
        replyBtn.addEventListener("click", function () {
            startReply(m);
        });
        menu.appendChild(replyBtn);

        var forwardBtn = iconButton("fas fa-share", t("chatForward", "Forward"));
        forwardBtn.addEventListener("click", function () {
            forwardMessage(m);
        });
        menu.appendChild(forwardBtn);

        if (m.mine) {
            var editBtn = iconButton("fas fa-pen", t("chatEdit", "Edit"));
            editBtn.addEventListener("click", function () {
                startEdit(m);
            });
            menu.appendChild(editBtn);

            var pinBtn = iconButton(
                m.is_pinned ? "fas fa-thumbtack ab-chat__pin--active" : "fas fa-thumbtack",
                m.is_pinned ? t("chatUnpin", "Unpin") : t("chatPin", "Pin")
            );
            pinBtn.addEventListener("click", function () {
                post(detailUrl(urls.chatPin, m.id), {})
                    .then(function (data) {
                        renderPinned(data.pinned);
                        var row = document.querySelector('.ab-chat__msg[data-id="' + m.id + '"]');
                        if (row) {
                            var icon = row.querySelector(".fa-thumbtack");
                            if (icon) icon.classList.toggle("ab-chat__pin--active", !!data.pinned);
                        }
                    })
                    .catch(function (err) {
                        toast((err && err.message) || t("chatError", "Something went wrong."), "error");
                    });
            });
            menu.appendChild(pinBtn);

            var delBtn = iconButton("fas fa-trash", t("chatDelete", "Delete"));
            delBtn.addEventListener("click", function () {
                if (!window.confirm(t("chatDeleteConfirm", "Delete this message for both sides?"))) return;
                post(detailUrl(urls.chatDelete, m.id), {})
                    .then(function () {
                        var row = document.querySelector('.ab-chat__msg[data-id="' + m.id + '"]');
                        if (row) row.replaceWith(renderMessage(Object.assign({}, m, { is_deleted: true })));
                    })
                    .catch(function (err) {
                        toast((err && err.message) || t("chatError", "Something went wrong."), "error");
                    });
            });
            menu.appendChild(delBtn);
        }
        return menu;
    }

    function iconButton(iconClass, title) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "ab-chat__iconbtn";
        btn.title = title;
        btn.setAttribute("aria-label", title);
        var icon = document.createElement("i");
        icon.className = iconClass;
        btn.appendChild(icon);
        return btn;
    }

    function scrollMessagesToBottom() {
        els.messages.scrollTop = els.messages.scrollHeight;
    }

    /* ------------------------------------------------------------------
       Compose: reply / edit / send / upload
    ------------------------------------------------------------------ */

    function startReply(m) {
        state.replyTo = m.id;
        els.replyBox.hidden = false;
        els.replyPreview.textContent = m.body || t("chatAttachment", "📎 Attachment");
        els.input.focus();
    }

    function startEdit(m) {
        els.input.value = m.body;
        state.replyTo = null;
        els.replyBox.hidden = true;
        state.editing = m.id;
        els.input.focus();
        els.send.querySelector("i").className = "fas fa-check";
    }

    function clearComposerModes() {
        state.replyTo = null;
        state.editing = null;
        els.replyBox.hidden = true;
        els.send.querySelector("i").className = "fas fa-paper-plane";
    }

    function sendMessage() {
        var body = els.input.value.trim();
        if (state.sending || !state.thread) return;

        if (state.editing) {
            if (!body) return;
            state.sending = true;
            post(detailUrl(urls.chatEdit, state.editing), { body: body })
                .then(function (data) {
                    state.sending = false;
                    els.input.value = "";
                    clearComposerModes();
                    upsertMessage(data.message);
                })
                .catch(function (err) {
                    state.sending = false;
                    // Leave edit mode even when the save failed: otherwise the
                    // next send retries the edit instead of sending the text
                    // the user sees in the composer.
                    clearComposerModes();
                    toast((err && err.message) || t("chatError", "Something went wrong."), "error");
                });
            return;
        }

        if (!body && !state.pendingAttachments.length) return;
        var payload = { partner: state.thread.peer.id, body: body };
        // Attachment-only send: an empty body is refused server-side unless the
        // files that justify it are declared here (they are uploaded to this
        // very message right after the POST resolves).
        if (!body && state.pendingAttachments.length) payload.has_files = true;
        if (state.replyTo) payload.reply_to = state.replyTo;
        // No conversation yet (a contact row): the send endpoint creates it and
        // answers with the new conversation id, which the upload endpoint and
        // the socket both need.
        var isNew = !state.activeId;

        state.sending = true;
        els.send.disabled = true;
        post(urls.chatSend, payload)
            .then(function (data) {
                els.input.value = "";
                state.replyTo = null;
                els.replyBox.hidden = true;
                var files = state.pendingAttachments.slice();
                state.pendingAttachments = [];
                // The chips in the hint are pure DOM state (the change handler
                // appends them, nothing else removed them), so clear them with
                // the state they mirror — otherwise a sent file keeps showing
                // as "pending" until the thread is reopened.
                renderFileHint();
                if (isNew) state.activeId = data.message.conversation;
                return uploadFiles(data.message, files).then(function () {
                    state.sending = false;
                    els.send.disabled = false;
                    if (isNew) {
                        // Fetch the freshly created thread so rows, read marker
                        // and history all come from the server.
                        openThread(state.activeId);
                    } else {
                        // The socket push for this very message can beat the
                        // HTTP response here, so upsert instead of append.
                        upsertMessage(data.message);
                        scrollMessagesToBottom();
                    }
                    loadConversations();
                });
            })
            .catch(function (err) {
                state.sending = false;
                els.send.disabled = false;
                toast((err && err.message) || t("chatError", "Something went wrong."), "error");
            });
    }

    function uploadFiles(messageRow, files) {
        var chain = Promise.resolve();
        files.forEach(function (file) {
            chain = chain.then(function () {
                var form = new FormData();
                form.append("file", file);
                return fetch(detailUrl(urls.chatUpload, state.activeId), {
                    method: "POST",
                    body: form,
                    headers: {
                        "X-CSRFToken": getCsrf(),
                        "X-Requested-With": "XMLHttpRequest",
                    },
                }).then(function (r) {
                    return r.json().then(function (data) {
                        if (!r.ok) throw data;
                        // The upload response carries the attachment in the
                        // very shape the message payload uses. Record it on
                        // the row now: the caller's final upsert repaints from
                        // THIS object, which still holds the pre-upload
                        // (attachment-less) copy — without this the paint
                        // erases the file the socket push just drew.
                        if (data.attachment) {
                            messageRow.attachments = messageRow.attachments || [];
                            messageRow.attachments.push(data.attachment);
                        }
                        return data;
                    });
                });
            });
        });
        return chain;
    }

    // One place owns "this message changed": the array entry and the row are
    // updated together, inserting when the row is not on screen yet.
    function upsertMessage(payload) {
        if (!state.thread) return;
        var idx = state.thread.messages.findIndex(function (m) {
            return m.id === payload.id;
        });
        if (idx >= 0) state.thread.messages[idx] = payload;
        else state.thread.messages.push(payload);
        var row = document.querySelector('.ab-chat__msg[data-id="' + payload.id + '"]');
        if (row) row.replaceWith(renderMessage(payload));
        else els.messages.appendChild(renderMessage(payload));
    }

    function forwardMessage(m) {
        // The id in the prompt is the PEER's user id, not the conversation id:
        // the endpoint resolves `partner` as a user to message (a conversation
        // id only ever matched by coincidence, so the forward was refused).
        var options = state.conversations
            .filter(function (c) {
                return c.id !== state.activeId;
            })
            .map(function (c) {
                return c.peer.name + " (id:" + c.peer.id + ")";
            })
            .join("\n");
        var choice = window.prompt(
            t("chatForwardPrompt", "Forward this message to which conversation?\n\n") + options
        );
        if (!choice) return;
        var match = choice.match(/id:(\d+)/);
        if (!match) return;
        post(detailUrl(urls.chatForward, m.id), { partner: Number(match[1]) })
            .then(function () {
                toast(t("chatForwardedDone", "Message forwarded."), "success");
            })
            .catch(function (err) {
                toast((err && err.message) || t("chatError", "Something went wrong."), "error");
            });
    }

    /* ------------------------------------------------------------------
       Attachments
    ------------------------------------------------------------------ */

    function wireAttachments() {
        els.attach.addEventListener("click", function () {
            if (!els.attach.disabled) els.file.click();
        });
        els.file.addEventListener("change", function () {
            var allowance = state.thread && state.thread.can_file;
            Array.prototype.slice.call(this.files).forEach(function (file) {
                if (allowance == null) {
                    toast(t("chatFileNotAllowed", "File sending is not enabled for your account."), "error");
                    return;
                }
                if (file.size > allowance * 1024 * 1024) {
                    toast(
                        t("chatFileTooBig", "This file is too large. Your limit is __MB MB.").replace(
                            "__MB",
                            String(allowance)
                        ),
                        "error"
                    );
                    return;
                }
                state.pendingAttachments.push(file);
                var chip = document.createElement("span");
                chip.className = "ab-chat__pending-file";
                chip.textContent = file.name;
                els.fileHint.appendChild(chip);
            });
            this.value = "";
        });
    }

    /* ------------------------------------------------------------------
       Typing
    ------------------------------------------------------------------ */

    function wireTyping() {
        els.input.addEventListener("input", function () {
            var now = Date.now();
            // At most one typing ping every 2s (the socket rate limit is 20/10s).
            if (!state.activeId || now - state.typingSentAt < 2000) return;
            state.typingSentAt = now;
            emit({ type: "chat.typing", conversation: state.activeId });
        });
    }

    function emit(payload) {
        document.dispatchEvent(new CustomEvent("ab:chat-send", { detail: payload }));
    }

    function sendRead() {
        if (!state.activeId) return;
        emit({ type: "chat.read", conversation: state.activeId });
        // Fallback: also record via HTTP so a dropped socket cannot keep the
        // thread unread forever.
        fetch(detailUrl(urls.chatRead, state.activeId), {
            method: "POST",
            headers: { "X-CSRFToken": getCsrf(), "X-Requested-With": "XMLHttpRequest" },
        }).catch(function () {});
    }

    /* ------------------------------------------------------------------
       Realtime events (dispatched by realtime.js from the chat socket)
    ------------------------------------------------------------------ */

    function onChatEvent(event) {
        // Another page may have replaced the fragment since the event was
        // queued; there is nothing of ours to update then.
        if (!document.getElementById("abChatRoot")) return;
        var d = event.detail || {};
        switch (d.type) {
            case "chat.message":
                onIncomingMessage(d);
                break;
            case "chat.message.update":
                // Only the thread on screen reacts; other conversations update
                // through their own list row and the next thread fetch.
                if (d.message && d.conversation === state.activeId) {
                    upsertMessage(d.message);
                }
                break;
            case "chat.read":
                onReadEvent(d);
                break;
            case "chat.typing":
                if (d.conversation === state.activeId) showTyping(!!d.typing);
                break;
            case "chat.presence":
                if (state.thread && state.thread.peer.id === d.user) {
                    setPeerStatus(d.online);
                    renderList();
                }
                break;
            case "chat.pinned":
                if (d.conversation === state.activeId) renderPinned(d.pinned);
                break;
            case "chat.refresh":
                loadConversations();
                break;
            case "chat.file.permission":
                if (state.thread) {
                    state.thread.can_file = d.max_file_mb;
                    renderFileHint();
                }
                break;
            default:
                break;
        }
    }

    function onIncomingMessage(d) {
        var mine = d.sender === (window.AppConfig && window.AppConfig.userId);
        if (d.conversation === state.activeId) {
            upsertMessage(d);
            scrollMessagesToBottom();
            sendRead();
        } else if (!mine) {
            // A message in a background conversation: a quiet toast with a
            // sender name so the user knows which thread lit up.
            var conversation = state.conversations.find(function (c) {
                return c.id === d.conversation;
            });
            var who = conversation ? conversation.peer.name : "";
            var what = d.body ? d.body.slice(0, 80) : t("chatAttachment", "📎 Attachment");
            toast(who ? who + ": " + what : what, "info");
        }
        loadConversations();
    }

    function onReadEvent(d) {
        if (!state.thread) return;
        // The peer read the thread: flip my ticks to double and remember when.
        if (d.reader && state.thread.peer.id === d.reader) {
            state.peerReadAt = d.last_read_at || state.peerReadAt;
            state.thread.messages.slice().forEach(function (m) {
                if (!m.mine || m.read) return;
                m.read = true;
                // Re-render the row: the double check carries the read time,
                // which a class swap alone could not add.
                upsertMessage(m);
            });
        }
    }

    var typingTimeout = null;
    function showTyping(active) {
        els.typing.hidden = !active;
        clearTimeout(typingTimeout);
        if (active) {
            typingTimeout = setTimeout(function () {
                els.typing.hidden = true;
            }, 4000);
        }
    }

    /* ------------------------------------------------------------------
       Wiring — split in two because fragments are re-injected: element
       listeners are rebound per fragment, document-level delegation only
       once per page load.
    ------------------------------------------------------------------ */

    function wireFragment() {
        els.back.addEventListener("click", closeThread);
        els.send.addEventListener("click", sendMessage);
        els.input.addEventListener("keydown", function (e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        els.replyCancel.addEventListener("click", function () {
            state.replyTo = null;
            els.replyBox.hidden = true;
        });
        wireAttachments();
        wireTyping();
    }

    /* ------------------------------------------------------------------
       File-permission grant modal (My Students rows + admin chat header).
       One shared dialog in the dashboard shell; a .chat-grant-btn anywhere
       opens it with that student's context.
    ------------------------------------------------------------------ */

    var grantStudentId = null;

    function bindDelegates() {
        if (delegatesBound) return;
        delegatesBound = true;

        document.addEventListener("ab:chat-event", onChatEvent);

        // A push that arrives before the page finished loading the list is
        // lost otherwise: re-sync once the socket (re)connects.
        document.addEventListener("ab:chat-connected", function () {
            if (document.getElementById("abChatRoot")) loadConversations();
        });

    document.addEventListener("click", function (e) {
        var btn = e.target.closest(".chat-grant-btn");
        if (!btn) return;
        grantStudentId = btn.dataset.studentId;
        var modal = document.getElementById("chatGrantModal");
        if (!modal) return;
        document.getElementById("chatGrantStudentName").textContent =
            btn.dataset.studentName || "";
        var mbInput = document.getElementById("chatGrantMb");
        var prefill = parseInt(btn.dataset.currentMb, 10);
        // A revoked grant keeps its row (is_active=False), so the stored MB
        // is stale: only an ACTIVE grant may seed the field, otherwise the
        // dialog would offer to "grant" a limit the student no longer has.
        var isActive = btn.dataset.currentActive === "True";
        if (prefill && isActive) {
            mbInput.value = prefill;
        } else {
            // No personal grant (or a revoked one): pre-fill the site default.
            mbInput.value = window.AppConfig.chatDefaultFileMb ||
                window.AppConfig.chat_default_file_mb || 5;
        }
        modal.classList.remove("hidden");
    });

    document.addEventListener("submit", function (e) {
        if (e.target.id !== "chatGrantForm") return;
        e.preventDefault();
        if (!grantStudentId) return;
        var mb = parseInt(document.getElementById("chatGrantMb").value, 10);
        if (!mb || mb < 1) return;
        post(detailUrl(urls.chatGrant, grantStudentId), { max_file_mb: mb })
            .then(function () {
                toast(t("chatGrantDone", "File permission updated."), "success");
                document.getElementById("chatGrantModal").classList.add("hidden");
            })
            .catch(function (err) {
                toast((err && err.message) || t("chatError", "Something went wrong."), "error");
            });
    });

    document.addEventListener("click", function (e) {
        if (!e.target.closest("#chatGrantRevoke")) return;
        if (!grantStudentId) return;
        if (!window.confirm(t("chatRevokeConfirm", "Revoke this student's file permission?"))) return;
        post(detailUrl(urls.chatGrant, grantStudentId), { revoke: true })
            .then(function () {
                toast(t("chatRevoked", "File permission revoked."), "success");
                document.getElementById("chatGrantModal").classList.add("hidden");
            })
            .catch(function (err) {
                toast((err && err.message) || t("chatError", "Something went wrong."), "error");
            });
    });
    }

    /* ------------------------------------------------------------------
       Bootstrap
    ------------------------------------------------------------------ */

    function initChatScripts() {
        bindDelegates();

        var root = document.getElementById("abChatRoot");
        urls = (window.AppConfig && window.AppConfig.urls) || {};
        if (!root || !urls.chatConversations) return;
        // The flag lives on the fragment element, so a re-injected shell
        // initialises again while a duplicate call for the same one does not.
        if (root.dataset.abChatReady === "1") return;
        root.dataset.abChatReady = "1";

        captureElements();
        state.conversations = [];
        state.contacts = [];
        state.canFile = null;
        state.activeId = null;
        state.thread = null;
        state.replyTo = null;
        state.pendingAttachments = [];
        state.sending = false;
        state.typingSentAt = 0;
        wireFragment();

        // Reopen a conversation after a refresh (?page=chat&chat=<id>).
        loadConversations().then(function () {
            var params = new URLSearchParams(window.location.search);
            var initial = Number(params.get("chat"));
            if (initial && state.conversations.some(function (c) { return c.id === initial; })) {
                openThread(initial);
            }
        });
    }

    // dashboard.js calls this right after injecting the fragment; the direct
    // calls cover a full page load that already contains the shell.
    window.initChatScripts = initChatScripts;
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initChatScripts);
    } else {
        initChatScripts();
    }
})();
