import React from 'react';

export default function ResearchInterestsEditor({ value, onChange, tags }) {
  return (
    <div className="tag-options">
      {tags
        .filter((tag) => tag.kind === 'INTEREST')
        .map((tag) => (
          <label className={`tag-option ${value.includes(tag.id) ? 'selected' : ''}`} key={tag.id}>
            <input
              type="checkbox"
              checked={value.includes(tag.id)}
              disabled={!value.includes(tag.id) && value.length >= 100}
              onChange={(e) =>
                onChange(
                  e.target.checked ? [...value, tag.id] : value.filter((id) => id !== tag.id)
                )
              }
            />
            {tag.label}
          </label>
        ))}
    </div>
  );
}
