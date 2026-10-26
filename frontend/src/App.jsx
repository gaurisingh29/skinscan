import React, { useEffect, useState } from "react";

const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = [
  "image/jpeg",
  "image/jpg",
  "image/pjpeg",
  "image/png",
  "image/x-png",
  "image/webp",
  "image/jfif",
  "image/bmp",
  "image/gif",
];

function isSupportedImage(file) {
  if (!file) return false;
  const fileType = (file.type || "").toLowerCase();
  const fileName = (file.name || "").toLowerCase();
  if (ALLOWED_IMAGE_TYPES.includes(fileType)) return true;
  if (fileType.startsWith("image/")) return true;
  return /\.(jpe?g|png|webp|jfif|bmp|gif|heic)$/i.test(fileName);
}

// Client-side image optimization to prevent Vercel 4.5MB serverless payload limit
async function optimizeImageForUpload(file) {
  if (file.size <= 2 * 1024 * 1024) {
    return file;
  }

  return new Promise((resolve) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      const maxDimension = 1600;
      let { width, height } = img;

      if (width > maxDimension || height > maxDimension) {
        if (width > height) {
          height = Math.round((height * maxDimension) / width);
          width = maxDimension;
        } else {
          width = Math.round((width * maxDimension) / height);
          height = maxDimension;
        }
      }

      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, width, height);

      canvas.toBlob(
        (blob) => {
          if (blob) {
            resolve(
              new File(
                [blob],
                file.name.replace(/\.[^.]+$/, ".jpg"),
                { type: "image/jpeg" }
              )
            );
          } else {
            resolve(file);
          }
        },
        "image/jpeg",
        0.88
      );
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(file);
    };

    img.src = url;
  });
}

function ResultList({ title, items }) {
  if (!items?.length) return null;

  return (
    <section className="result-section">
      <h3>{title}</h3>
      <ul>
        {items.map((item, index) => (
          <li key={`${title}-${index}`}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

export default function App() {
  const [photo, setPhoto] = useState(null);
  const [preview, setPreview] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [consent, setConsent] = useState(false);

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  function choosePhoto(event) {
    const selected = event.target.files?.[0];
    event.target.value = "";
    if (!selected) return;

    if (!isSupportedImage(selected)) {
      setError("Please choose a valid photo (JPEG, PNG, WebP, etc.).");
      return;
    }
    if (selected.size > MAX_IMAGE_BYTES) {
      setError("Your photo must be 10 MB or smaller.");
      return;
    }

    setPhoto(selected);
    setPreview(URL.createObjectURL(selected));
    setAnalysis(null);
    setError("");
    setConsent(true);
  }

  async function analyzePhoto(event) {
    event.preventDefault();
    if (!photo || loading) return;

    setLoading(true);
    setError("");
    setAnalysis(null);

    try {
      const fileToSend = await optimizeImageForUpload(photo);
      const formData = new FormData();
      formData.append("image", fileToSend);

      const response = await fetch("/api/analyze", {
        method: "POST",
        body: formData,
      });

      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "Analysis could not be completed.");
      }
      setAnalysis(result);
    } catch (requestError) {
      setError(requestError.message || "Could not reach the skincare advisor.");
    } finally {
      setLoading(false);
    }
  }

  function removePhoto() {
    setPhoto(null);
    setPreview("");
    setAnalysis(null);
    setError("");
  }

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Skin Notes home">
          <span className="brand-mark" aria-hidden="true">s</span>
          <span>skin notes</span>
        </a>
        <span className="topbar-note">A little care, a little clarity</span>
      </header>

      <section className="intro">
        <p className="eyebrow">YOUR PERSONAL SKINCARE STARTING POINT</p>
        <h1>Get to know<br />your skin.</h1>
        <p className="intro-copy">
          Share a clear photo for gentle, practical skincare suggestions made
          around what’s visible.
        </p>
      </section>

      <section className="advisor-card" aria-label="Skin photo analysis">
        <form onSubmit={analyzePhoto}>
          <div className="card-heading">
            <div>
              <span className="step-label">01 / YOUR PHOTO</span>
              <h2>A fresh-faced moment</h2>
            </div>
            <span className="leaf-icon" aria-hidden="true">✳</span>
          </div>

          <label className={`upload-area ${preview ? "has-photo" : ""}`}>
            <input
              type="file"
              accept="image/*"
              capture="user"
              onChange={choosePhoto}
            />
            {preview ? (
              <>
                <img className="photo-preview" src={preview} alt="Selected face photo" />
                <span className="change-photo">Choose another photo</span>
              </>
            ) : (
              <span className="upload-prompt">
                <span className="upload-icon" aria-hidden="true">↑</span>
                <strong>Upload or take a photo</strong>
                <span>JPG, PNG or WebP · any photo</span>
                <span className="camera-hint">A clear, natural-light photo works best</span>
              </span>
            )}
          </label>

          {preview && (
            <div className="selected-file">
              <span>{photo?.name}</span>
              <button type="button" className="text-button" onClick={removePhoto}>
                Remove
              </button>
            </div>
          )}

          <label className="consent-note">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
              required
            />
            <span>
              I understand my photo will be sent for analysis and will
              not be saved by this app.
            </span>
          </label>

          <button
            className="analyze-button"
            type="submit"
            disabled={!photo || !consent || loading}
          >
            {loading ? (
              <>
                <span className="spinner" aria-hidden="true" />
                Looking closely…
              </>
            ) : (
              <>Explore my skin <span aria-hidden="true">↗</span></>
            )}
          </button>
        </form>
      </section>

      {error && <p className="error-message" role="alert">{error}</p>}

      {analysis && (
        <section className="results-card" aria-live="polite">
          <p className="eyebrow">02 / YOUR NOTES</p>
          <h2>A gentle place to begin</h2>
          <p className="result-summary">{analysis.summary}</p>
          <div className="skin-type">
            <span>Possible skin type</span>
            <strong>{analysis.skin_type_guess}</strong>
          </div>
          <ResultList title="What may be visible" items={analysis.concerns} />
          <div className="routine-grid">
            <ResultList title="Morning" items={analysis.morning_routine} />
            <ResultList title="Evening" items={analysis.evening_routine} />
          </div>
          <ResultList title="A few cautions" items={analysis.cautions} />
          <div className="professional-note">
            <strong>When to check with a professional</strong>
            <p>{analysis.professional_care}</p>
          </div>
          <p className="disclaimer">
            AI-generated cosmetic guidance only — not a diagnosis or medical advice.
          </p>
        </section>
      )}

      <footer className="page-footer">
        <span>Care that starts with listening.</span>
        <span>Not medical advice · See a dermatologist for skin concerns</span>
      </footer>
    </main>
  );
}
