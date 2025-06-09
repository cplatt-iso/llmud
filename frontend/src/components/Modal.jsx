import React, { useState, useEffect, useRef } from 'react';
import './Modal.css';

function Modal({ isOpen, onClose, title, children, initialPosition = { x: 150, y: 150 } }) {
  const [position, setPosition] = useState(initialPosition);
  const [isDragging, setIsDragging] = useState(false);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const modalRef = useRef(null); // Ref to the modal div

  // This effect handles the 'mousemove' and 'mouseup' events.
  // We add them to the whole window so you can drag outside the modal's bounds.
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging) return;
      // Calculate new position based on initial mouse offset
      setPosition({
        x: e.clientX - offset.x,
        y: e.clientY - offset.y,
      });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    // Only listen for mouse movements when we are actively dragging
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    // Cleanup function to remove the listeners when the component unmounts
    // or when we stop dragging. This is CRITICAL to prevent memory leaks.
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, offset]);

  // This function kicks off the drag operation.
  const handleMouseDown = (e) => {
    // We only want to drag by the header, not the whole modal body.
    if (modalRef.current && modalRef.current.contains(e.target)) {
      setIsDragging(true);
      // Calculate the offset of the mouse from the top-left corner of the modal
      const modalRect = e.currentTarget.getBoundingClientRect();
      setOffset({
        x: e.clientX - modalRect.left,
        y: e.clientY - modalRect.top
      });
      // Prevent default browser behavior, like text selection
      e.preventDefault();
    }
  };


  if (!isOpen) {
    return null;
  }

  // The outer div is gone. The modal is now the root.
  // It has its own position style, and we've removed the backdrop click.
  return (
    <div
      ref={modalRef}
      className="draggable-window"
      style={{
        top: `${position.y}px`,
        left: `${position.x}px`,
      }}
    >
      <div
        className="modal-header"
        onMouseDown={handleMouseDown} // The header is now our drag handle
      >
        <h3 className="modal-title">{title}</h3>
        <button className="modal-close-button" onClick={onClose}>
          ×
        </button>
      </div>
      <div className="modal-body">{children}</div>
    </div>
  );
}

export default Modal;