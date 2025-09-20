const loginScreen = document.getElementById("login-screen");
const mainContent = document.getElementById("main-content");
const loginFormContainer = document.getElementById("login-form-container");
const registerFormContainer = document.getElementById("register-form-container");
const showLoginButton = document.getElementById("show-login");
const showRegisterButton = document.getElementById("show-register");
const emailInput = document.getElementById("email-input");
const passwordInput = document.getElementById("password-input");
const authError = document.getElementById("auth-error");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const registerEmail = document.getElementById("register-email");
const registerUsername = document.getElementById("register-username");
const registerPassword = document.getElementById("register-password");
const registerFirstName = document.getElementById("register-firstName");
const registerSurname = document.getElementById("register-surname");
const registerRequestTimeline = document.getElementById("register-requestTimeline");

const addEventSection = document.getElementById("add-event-section");
const timelineContainer = document.getElementById("timeline");
const eventForm = document.getElementById("event-form");
const imageFileInput = document.getElementById("image-file");
const clearFormButton = document.getElementById("clear-form");

const imageOverlay = document.getElementById("image-overlay");
const overlayImage = imageOverlay ? imageOverlay.querySelector("img") : null;

const timelineSelect = document.getElementById("timeline-select");
const loadingOverlay = document.getElementById("loading-overlay");
const taskbar = document.getElementById("taskbar");
const logoutButton = document.getElementById("logout-button");
const addTimelineButton = document.getElementById("add-timeline-button");
const selectedTimelineDisplay = document.getElementById("selected-timeline");
const timelineError = document.getElementById("timeline-error");

const cropperImage = document.getElementById("cropper-image");
const aspectRatioSelect = document.getElementById("aspect-ratio");
const cropConfirm = document.getElementById("crop-confirm");
const cropperModal = document.getElementById("cropper-modal");
const cropperPlaceholder = document.getElementById("cropper-placeholder");
const cropperControls = document.getElementById("cropper-controls");

let isAdmin = false;
let cropper = null;
let croppedBlob = null;
let originalFile = null;
let currentOriginalFileKey = null;
let currentCroppedFileKey = null;
let isEditingExistingImage = false;
let currentTimelineName = null;
let currentUser = null;

const API_ENDPOINT = "https://kx0nf3ttba.execute-api.eu-west-1.amazonaws.com/prod";
const S3_MEDIA_URL = "https://evidence-timeline-media.s3.eu-west-1.amazonaws.com";

function showLoadingSpinner() {
    if (loadingOverlay) {
        loadingOverlay.style.display = "flex";
        document.querySelectorAll("button, input, textarea, select").forEach(el => {
            el.disabled = true;
        });
    }
}

function hideLoadingSpinner() {
    if (loadingOverlay) {
        loadingOverlay.style.display = "none";
        // Only disable buttons, inputs, and textareas in #add-event-section and other buttons/inputs, excluding #timeline-select
        document.querySelectorAll(
            "#add-event-section button, #add-event-section input, #add-event-section textarea, " +
            "button:not(#add-timeline-button, #logout-button, #show-login, #show-register), " +
            "input:not(#timeline-select), textarea:not(#timeline-select)"
        ).forEach(el => {
            el.disabled = isAdmin && !currentTimelineName;
        });
        // Ensure #timeline-select, #add-timeline-button, and #logout-button are always enabled
        if (timelineSelect) {
            timelineSelect.disabled = false;
        }
        if (addTimelineButton && ['timeline_admin', 'super_admin'].includes(currentUser?.role)) {
            addTimelineButton.disabled = false;
        }
        if (logoutButton) {
            logoutButton.disabled = false;
        }
    }
}

async function fetchTimelines() {
    console.log("Fetching timelines with currentUser:", currentUser);
    console.log("X-Auth-Email to be sent:", currentUser ? currentUser.email : "undefined");
    const headers = {
        "Content-Type": "application/json",
        "X-Auth-Email": currentUser ? currentUser.email : ""
    };
    console.log("Request headers:", headers);
    try {
        const response = await fetch(`${API_ENDPOINT}/timelines`, {
            method: "GET",
            headers: headers,
        });
        console.log("Response status:", response.status, "Headers:", Object.fromEntries(response.headers));
        if (!response.ok) {
            const data = await response.json();
            console.log("Error response:", data);
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        const data = await response.json();
        console.log("Timelines data:", data);
        
        // Clear existing options
        if (timelineSelect) {
            timelineSelect.innerHTML = '<option value="">Select a timeline</option>';
        }
        
        // Populate dropdown with timelines
        if (data.timelines && Array.isArray(data.timelines)) {
            data.timelines.forEach(timeline => {
                const option = document.createElement("option");
                option.value = timeline;
                option.textContent = timeline === currentUser.username && currentUser.role === 'timeline_admin' 
                    ? `${timeline} (My Timeline)` 
                    : timeline;
                if (timelineSelect) {
                    timelineSelect.appendChild(option);
                }
            });
        } else {
            console.warn("No timelines found or invalid data:", data);
        }

        // Set currentTimelineName to the first timeline or null
        if (data.timelines && data.timelines.length > 0) {
            currentTimelineName = data.timelines[0];
            if (timelineSelect) {
                timelineSelect.value = currentTimelineName;
            }
            if (selectedTimelineDisplay) {
                selectedTimelineDisplay.textContent = currentTimelineName === currentUser.username && currentUser.role === 'timeline_admin' 
                    ? `${currentTimelineName} (My Timeline)` 
                    : currentTimelineName;
            }
        } else {
            currentTimelineName = null;
            if (selectedTimelineDisplay) {
                selectedTimelineDisplay.textContent = "No Timeline Selected";
            }
        }

        // Enable/disable buttons based on timeline selection
        if (isAdmin && addEventSection) {
            document.querySelectorAll("#add-event-section button").forEach(btn => {
                btn.disabled = !currentTimelineName;
            });
        }

        // Render the selected timeline
        await renderTimeline();
    } catch (error) {
        console.error("Error fetching timelines:", error);
        if (timelineError) {
            timelineError.textContent = "Error loading timelines. Please try again.";
            timelineError.style.display = "block";
        }
    } finally {
        hideLoadingSpinner();
    }
}

async function addTimeline() {
    if (!currentUser || !['timeline_admin', 'super_admin'].includes(currentUser.role)) {
        if (authError) authError.textContent = "You do not have permission to add timelines.";
        return;
    }
    const timelineName = prompt("Enter timeline name:");
    if (!timelineName || timelineName.trim() === "") {
        if (authError) authError.textContent = "Timeline name cannot be empty.";
        return;
    }
    showLoadingSpinner();
    try {
        const response = await fetch(`${API_ENDPOINT}/timelines`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Auth-Email": currentUser.email
            },
            body: JSON.stringify({ timelineName: timelineName.trim() })
        });
        const data = await response.json();
        if (response.ok && data.message) {
            await fetchTimelines();
            if (authError) authError.textContent = "Timeline added successfully.";
        } else {
            if (authError) authError.textContent = data.error || "Error adding timeline.";
        }
    } catch (error) {
        console.error("Error adding timeline:", error);
        if (authError) authError.textContent = "Failed to add timeline. Please try again.";
    } finally {
        hideLoadingSpinner();
    }
}

function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

async function renderTimeline() {
    if (!currentTimelineName) {
        if (timelineContainer) timelineContainer.innerHTML = "";
        if (isAdmin && authError) {
            authError.textContent = "Please select a timeline to view or manage events.";
        }
        hideLoadingSpinner();
        return;
    }
    showLoadingSpinner();
    try {
        const response = await fetch(`${API_ENDPOINT}/events?timelineName=${encodeURIComponent(currentTimelineName)}`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
                "X-Auth-Email": currentUser ? currentUser.email : ""
            },
        });
        if (!response.ok) {
            const data = await response.json();
            throw new Error(`HTTP error! Status: ${response.status} ${data.error || response.statusText}`);
        }
        const data = await response.json();
        const timelineEvents = data.events || [];
        hideLoadingSpinner();
        if (timelineContainer) timelineContainer.innerHTML = "";

        const groups = {};
        timelineEvents.forEach(event => {
            const dateKey = event.date.split("T")[0];
            if (!groups[dateKey]) groups[dateKey] = [];
            groups[dateKey].push(event);
        });

        const sortedDates = Object.keys(groups).sort();

        for (const date of sortedDates) {
            const dateMarker = document.createElement("div");
            dateMarker.className = "date-marker";
            dateMarker.textContent = formatDate(date);
            if (timelineContainer) timelineContainer.appendChild(dateMarker);

            groups[date].forEach(event => {
                const eventDiv = document.createElement("div");
                eventDiv.className = "timeline-event";
                eventDiv.dataset.eventId = event.eventId;

                const mediaContainer = document.createElement("div");

                if (event.croppedFileKey) {
                    const fileType = event.croppedFileKey.match(/\.(jpg|jpeg|png|ogg|mp3)$/i) ? 
                        (event.croppedFileKey.match(/\.(jpg|jpeg|png)$/i) ? "image" : "audio") : null;
                    if (fileType === "image") {
                        const img = document.createElement("img");
                        img.src = `${S3_MEDIA_URL}/${event.croppedFileKey}?t=${new Date().getTime()}`;
                        img.alt = "Event image";
                        img.addEventListener("click", () => {
                            if (overlayImage) {
                                overlayImage.src = img.src;
                                if (imageOverlay) imageOverlay.style.display = "flex";
                            }
                        });
                        img.onerror = () => {
                            console.error(`Failed to load image: ${img.src}`);
                            img.style.display = "none";
                        };
                        mediaContainer.appendChild(img);
                    } else if (fileType === "audio") {
                        const audio = document.createElement("audio");
                        audio.controls = true;
                        audio.src = `${S3_MEDIA_URL}/${event.croppedFileKey}`;
                        audio.onerror = () => {
                            console.error(`Failed to load audio: ${audio.src}`);
                            audio.style.display = "none";
                        };
                        mediaContainer.appendChild(audio);
                    } else {
                        console.warn(`Unsupported file type for croppedFileKey: ${event.croppedFileKey}`);
                    }
                }

                const infoDiv = document.createElement("div");
                infoDiv.className = "event-info";

                const timeDiv = document.createElement("div");
                timeDiv.className = "event-time";
                timeDiv.textContent = new Date(event.date).toLocaleString();

                const descDiv = document.createElement("div");
                descDiv.textContent = event.description;

                infoDiv.appendChild(timeDiv);
                infoDiv.appendChild(descDiv);

                if (isAdmin && currentTimelineName) {
                    const buttonContainer = document.createElement("div");
                    buttonContainer.style.marginTop = "10px";

                    const editButton = document.createElement("button");
                    editButton.textContent = "Edit";
                    editButton.style.marginRight = "10px";
                    editButton.addEventListener("click", () => editEvent(event));
                    buttonContainer.appendChild(editButton);

                    const deleteButton = document.createElement("button");
                    deleteButton.textContent = "Delete";
                    deleteButton.addEventListener("click", () => deleteEvent(event.eventId));
                    buttonContainer.appendChild(deleteButton);

                    infoDiv.appendChild(buttonContainer);
                }

                eventDiv.appendChild(mediaContainer);
                eventDiv.appendChild(infoDiv);
                if (timelineContainer) timelineContainer.appendChild(eventDiv);
            });
        }
    } catch (error) {
        console.error("Error fetching timeline:", error);
        hideLoadingSpinner();
        if (authError) authError.textContent = `Error loading timeline: ${error.message}. Please try again.`;
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const email = emailInput ? emailInput.value.trim() : "";
    const password = passwordInput ? passwordInput.value.trim() : "";
    if (!email || !password) {
        if (authError) authError.textContent = "Please enter email and password";
        return;
    }
    try {
        const response = await fetch(`${API_ENDPOINT}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
        });
        const data = await response.json();
        if (response.ok && data.authenticated) {
            isAdmin = data.isAdmin;
            currentUser = { 
                email: data.email, 
                role: data.role, 
                timelines: data.timelines, 
                username: data.username 
            };
            localStorage.setItem('user', JSON.stringify(currentUser));
            loginSuccess();
        } else {
            if (authError) authError.textContent = data.error || "Incorrect email or password";
        }
    } catch (error) {
        console.error("Login error:", error);
        if (authError) authError.textContent = "Error during login. Please try again.";
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const email = registerEmail ? registerEmail.value.trim() : "";
    const username = registerUsername ? registerUsername.value.trim() : "";
    const password = registerPassword ? registerPassword.value.trim() : "";
    const firstName = registerFirstName ? registerFirstName.value.trim() : "";
    const surname = registerSurname ? registerSurname.value.trim() : "";
    const requestTimeline = registerRequestTimeline ? registerRequestTimeline.checked : false;

    if (!email || !username || !password || !firstName || !surname) {
        if (authError) authError.textContent = "Please fill in all required fields";
        return;
    }

    try {
        const response = await fetch(`${API_ENDPOINT}/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, username, password, firstName, surname, requestTimeline }),
        });
        const data = await response.json();
        if (response.ok && data.message) {
            if (authError) authError.textContent = "Registration successful! Please log in.";
            showLogin();
            if (registerForm) registerForm.reset();
        } else {
            if (authError) authError.textContent = data.error || "Error during registration";
        }
    } catch (error) {
        console.error("Registration error:", error);
        if (authError) authError.textContent = "Failed to connect to server. Please try again later.";
    }
}

function showLogin() {
    if (loginFormContainer) loginFormContainer.style.display = "block";
    if (registerFormContainer) registerFormContainer.style.display = "none";
    if (showLoginButton) showLoginButton.classList.add("active");
    if (showRegisterButton) showRegisterButton.classList.remove("active");
    if (authError) authError.textContent = "";
}

function showRegister() {
    if (loginFormContainer) loginFormContainer.style.display = "none";
    if (registerFormContainer) registerFormContainer.style.display = "block";
    if (showLoginButton) showLoginButton.classList.remove("active");
    if (showRegisterButton) showRegisterButton.classList.add("active");
    if (authError) authError.textContent = "";
}

if (loginForm) {
    loginForm.addEventListener("submit", handleLogin);
}

if (registerForm) {
    registerForm.addEventListener("submit", handleRegister);
}

if (showLoginButton) {
    showLoginButton.addEventListener("click", showLogin);
}

if (showRegisterButton) {
    showRegisterButton.addEventListener("click", showRegister);
}

function loginSuccess() {
    console.log("Login success, currentUser:", currentUser);
    if (loginScreen) loginScreen.style.display = "none";
    if (mainContent) mainContent.style.display = "block";
    if (taskbar) taskbar.style.display = "flex";
    if (addEventSection) addEventSection.style.display = isAdmin ? "block" : "none";
    if (addTimelineButton && ['timeline_admin', 'super_admin'].includes(currentUser?.role)) {
        addTimelineButton.style.display = "inline-block";
        addTimelineButton.disabled = false;
    }
    if (logoutButton) {
        logoutButton.style.display = "inline-block";
        logoutButton.disabled = false;
    }
    if (selectedTimelineDisplay) selectedTimelineDisplay.textContent = "No Timeline Selected";
    if (emailInput) emailInput.value = "";
    if (passwordInput) passwordInput.value = "";
    if (authError) authError.textContent = "";
    if (timelineError) {
        timelineError.textContent = "";
        timelineError.style.display = "none";
    }
    if (isAdmin) {
        document.querySelectorAll("#add-event-section button").forEach(btn => {
            btn.disabled = true;
        });
    }
    fetchTimelines();
}

if (imageFileInput && cropperImage && cropperModal && cropperPlaceholder && cropConfirm && cropperControls) {
    imageFileInput.addEventListener("change", () => {
        const file = imageFileInput.files[0];
        if (file && file.type.startsWith("image/")) {
            originalFile = file;
            const reader = new FileReader();
            reader.onload = () => {
                cropperImage.src = reader.result;
                cropperModal.style.display = "block";
                cropperPlaceholder.style.display = "none";
                cropperImage.style.display = "block";
                cropperControls.style.display = "flex";
                cropConfirm.style.display = "block";
                if (cropper) cropper.destroy();
                cropper = new Cropper(cropperImage, {
                    viewMode: 1,
                    aspectRatio: aspectRatioSelect && aspectRatioSelect.value ? parseFloat(aspectRatioSelect.value) : NaN,
                    minCropBoxWidth: 10,
                    minCropBoxHeight: 10,
                });
            };
            reader.onerror = () => {
                console.error("Error reading file:", file?.name);
                if (authError) authError.textContent = "Error reading file";
            };
            reader.readAsDataURL(file);
        } else {
            cropperModal.style.display = "none";
            cropperPlaceholder.style.display = "none";
            cropperImage.style.display = "none";
            cropperControls.style.display = "none";
            cropConfirm.style.display = "none";
            if (cropper) cropper.destroy();
            cropper = null;
            croppedBlob = file;
            originalFile = file;
            currentOriginalFileKey = null;
            currentCroppedFileKey = null;
        }
    });
}

if (aspectRatioSelect) {
    aspectRatioSelect.addEventListener("change", () => {
        if (cropper) {
            cropper.setAspectRatio(aspectRatioSelect.value ? parseFloat(aspectRatioSelect.value) : NaN);
        }
    });
}

if (cropConfirm) {
    cropConfirm.addEventListener("click", () => {
        if (!cropper) return;
        const croppedCanvas = cropper.getCroppedCanvas();
        if (!croppedCanvas || croppedCanvas.width === 0 || croppedCanvas.height === 0) {
            if (authError) authError.textContent = "Invalid crop area. Please adjust the crop box and try again.";
            return;
        }
        croppedCanvas.toBlob(blob => {
            const fileType = imageFileInput && imageFileInput.files[0]?.type || "image/png";
            croppedBlob = new File([blob], `cropped_${imageFileInput && imageFileInput.files[0]?.name || "image.png"}`, { type: fileType });
            if (cropperModal) cropperModal.style.display = "none";
            if (cropperPlaceholder) cropperPlaceholder.style.display = "none";
            if (cropperImage) cropperImage.style.display = "none";
            if (cropperControls) cropperControls.style.display = "none";
            if (cropConfirm) cropConfirm.style.display = "none";
            if (cropper) {
                cropper.destroy();
                cropper = null;
            }
        }, imageFileInput && imageFileInput.files[0]?.type || "image/png");
    });
}

if (clearFormButton) {
    clearFormButton.addEventListener("click", () => {
        if (eventForm) eventForm.reset();
        delete eventForm.dataset.eventId;
        croppedBlob = null;
        originalFile = null;
        currentOriginalFileKey = null;
        currentCroppedFileKey = null;
        isEditingExistingImage = false;
        if (cropperModal) cropperModal.style.display = "none";
        if (cropperPlaceholder) cropperPlaceholder.style.display = "none";
        if (cropperImage) cropperImage.style.display = "none";
        if (cropperControls) cropperControls.style.display = "none";
        if (cropConfirm) cropConfirm.style.display = "none";
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
        if (eventForm) {
            const submitButton = eventForm.querySelector("button[type='submit']");
            if (submitButton) submitButton.textContent = "Add Event";
        }
        if (authError) authError.textContent = "";
    });
}

if (eventForm) {
    eventForm.addEventListener("submit", async e => {
        e.preventDefault();
        if (!currentTimelineName) {
            if (authError) authError.textContent = "Please select a timeline to add or update an event.";
            return;
        }
        showLoadingSpinner();
        const dateInput = document.getElementById("event-time");
        const descriptionInput = document.getElementById("event-text");
        const date = dateInput ? dateInput.value : "";
        const description = descriptionInput ? descriptionInput.value.trim() : "";
        const eventId = eventForm.dataset.eventId || null;

        if (!date || !description) {
            if (authError) authError.textContent = "Please fill in all required fields";
            hideLoadingSpinner();
            return;
        }

        const eventData = {
            date: date,
            description: description,
            timelineName: currentTimelineName
        };

        if (croppedBlob || originalFile) {
            const readFile = (file) => {
                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () => resolve(reader.result);
                    reader.onerror = () => reject(new Error(`Error reading file: ${file?.name}`));
                    reader.readAsDataURL(file);
                });
            };

            try {
                if (originalFile) {
                    eventData.originalFile = await readFile(originalFile);
                }
                if (croppedBlob) {
                    eventData.croppedFile = await readFile(croppedBlob);
                }
                await sendEvent(eventData, eventId);
            } catch (error) {
                console.error("Error reading files:", error);
                hideLoadingSpinner();
                if (authError) authError.textContent = "Error reading files";
            }
        } else {
            await sendEvent(eventData, eventId);
        }
    });
}

async function sendEvent(eventData, eventId) {
    try {
        showLoadingSpinner();
        const response = await fetch(`${API_ENDPOINT}/events${eventId ? `/${eventId}` : ""}`, {
            method: eventId ? "PUT" : "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Auth-Email": currentUser ? currentUser.email : ""
            },
            body: JSON.stringify(eventData),
        });
        const data = await response.json();
        if (response.ok && (data.message === "Event added" || data.message === "Event updated")) {
            if (eventForm) {
                eventForm.reset();
                delete eventForm.dataset.eventId;
            }
            croppedBlob = null;
            originalFile = null;
            currentOriginalFileKey = null;
            currentCroppedFileKey = null;
            isEditingExistingImage = false;
            if (cropperModal) cropperModal.style.display = "none";
            if (cropperPlaceholder) cropperPlaceholder.style.display = "none";
            if (cropperImage) cropperImage.style.display = "none";
            if (cropperControls) cropperControls.style.display = "none";
            if (cropConfirm) cropConfirm.style.display = "none";
            if (cropper) {
                cropper.destroy();
                cropper = null;
            }
            if (eventForm) {
                const submitButton = eventForm.querySelector("button[type='submit']");
                if (submitButton) submitButton.textContent = "Add Event";
            }
            renderTimeline();
            hideLoadingSpinner();
        } else {
            console.error("Error processing event:", data);
            hideLoadingSpinner();
            if (authError) authError.textContent = data.error || `Error saving event: ${JSON.stringify(data)}`;
        }
    } catch (error) {
        console.error("Fetch error:", error);
        hideLoadingSpinner();
        if (authError) authError.textContent = `Error saving event: ${error.message}. Please try again.`;
    }
}

async function editEvent(event) {
    if (!currentTimelineName) {
        if (authError) authError.textContent = "Please select a timeline to edit events.";
        return;
    }
    const eventTimeInput = document.getElementById("event-time");
    const eventTextInput = document.getElementById("event-text");
    if (eventTimeInput) eventTimeInput.value = event.date;
    if (eventTextInput) eventTextInput.value = event.description;
    if (eventForm) eventForm.dataset.eventId = event.eventId;
    currentTimelineName = event.timelineName;
    if (timelineSelect) timelineSelect.value = currentTimelineName;
    if (selectedTimelineDisplay) selectedTimelineDisplay.textContent = currentTimelineName === currentUser.username && currentUser.role === 'timeline_admin' ? `${currentTimelineName} (My Timeline)` : currentTimelineName;
    if (eventForm) {
        const submitButton = eventForm.querySelector("button[type='submit']");
        if (submitButton) submitButton.textContent = "Update Event";
    }
    croppedBlob = null;
    originalFile = null;
    currentOriginalFileKey = event.originalFileKey;
    currentCroppedFileKey = event.croppedFileKey;
    isEditingExistingImage = event.originalFileKey && event.originalFileKey.match(/\.(jpg|jpeg|png)$/i);
    if (isEditingExistingImage && cropperImage && cropperModal && cropperPlaceholder && cropperControls && cropConfirm) {
        cropperImage.src = `${S3_MEDIA_URL}/${event.originalFileKey}?t=${new Date().getTime()}`;
        cropperModal.style.display = "block";
        cropperPlaceholder.style.display = "none";
        cropperImage.style.display = "block";
        cropperControls.style.display = "flex";
        cropConfirm.style.display = "block";
        if (cropper) cropper.destroy();
        cropper = new Cropper(cropperImage, {
            viewMode: 1,
            aspectRatio: aspectRatioSelect && aspectRatioSelect.value ? parseFloat(aspectRatioSelect.value) : NaN,
            minCropBoxWidth: 10,
            minCropBoxHeight: 10,
        });
    } else {
        if (cropperModal) cropperModal.style.display = "none";
        if (cropperPlaceholder) cropperPlaceholder.style.display = "none";
        if (cropperImage) cropperImage.style.display = "none";
        if (cropperControls) cropperControls.style.display = "none";
        if (cropConfirm) cropConfirm.style.display = "none";
        if (cropper) {
            cropper.destroy();
            cropper = null;
        }
    }
}

async function deleteEvent(eventId) {
    if (!currentTimelineName) {
        if (authError) authError.textContent = "Please select a timeline to delete events.";
        return;
    }
    if (!confirm("Are you sure you want to delete this event?")) return;
    showLoadingSpinner();
    try {
        const response = await fetch(`${API_ENDPOINT}/events/${eventId}?timelineName=${encodeURIComponent(currentTimelineName)}`, {
            method: "DELETE",
            headers: {
                "Content-Type": "application/json",
                "X-Auth-Email": currentUser ? currentUser.email : ""
            },
        });
        const data = await response.json();
        if (data.success) {
            renderTimeline();
            hideLoadingSpinner();
        } else {
            hideLoadingSpinner();
            if (authError) authError.textContent = `Error deleting event: ${data.error || data.message}`;
        }
    } catch (error) {
        console.error("Error deleting event:", error);
        hideLoadingSpinner();
        if (authError) authError.textContent = `Error deleting event: ${error.message}. Please try again.`;
    }
}

if (imageOverlay) {
    imageOverlay.addEventListener("click", () => {
        imageOverlay.style.display = "none";
        if (overlayImage) overlayImage.src = "";
    });
}

if (timelineSelect) {
    timelineSelect.addEventListener("change", () => {
        currentTimelineName = timelineSelect.value || null;
        if (selectedTimelineDisplay) selectedTimelineDisplay.textContent = currentTimelineName === currentUser.username && currentUser.role === 'timeline_admin' ? `${currentTimelineName} (My Timeline)` : currentTimelineName || "No Timeline Selected";
        if (isAdmin) {
            document.querySelectorAll("#add-event-section button").forEach(btn => {
                btn.disabled = !currentTimelineName;
            });
        }
        if (authError) authError.textContent = "";
        if (timelineError) {
            timelineError.textContent = "";
            timelineError.style.display = "none";
        }
        renderTimeline();
    });
}

if (addTimelineButton) {
    addTimelineButton.addEventListener("click", addTimeline);
}

if (logoutButton) {
    logoutButton.addEventListener("click", () => {
        if (mainContent) mainContent.style.display = "none";
        if (loginScreen) loginScreen.style.display = "block";
        if (taskbar) taskbar.style.display = "none";
        isAdmin = false;
        currentUser = null;
        localStorage.removeItem('user');
        if (emailInput) emailInput.value = "";
        if (passwordInput) passwordInput.value = "";
        if (registerForm) registerForm.reset();
        if (authError) authError.textContent = "";
        if (timelineError) {
            timelineError.textContent = "";
            timelineError.style.display = "none";
        }
        isEditingExistingImage = false;
        currentTimelineName = null;
        if (timelineSelect) timelineSelect.value = "";
        if (selectedTimelineDisplay) selectedTimelineDisplay.textContent = "No Timeline Selected";
        if (addTimelineButton) addTimelineButton.style.display = "none";
        showLogin();
    });
}

// Check if user is already logged in
const storedUser = localStorage.getItem('user');
if (storedUser) {
    currentUser = JSON.parse(storedUser);
    isAdmin = currentUser.role === 'super_admin' || currentUser.role === 'timeline_admin';
    loginSuccess();
}