import pygame
import chess
import os
import sys
import re
import time
import threading
import queue
import numpy as np  # Moved to global import for clarity
import vosk
import pyaudio
import json

# Initialize Pygame
pygame.init()

# Set up the display
WIDTH, HEIGHT = 600, 650
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption('Offline Voice Chess')

# Initialize the chess board
board = chess.Board()

# Color constants
WHITE = (255, 255, 255)
GREEN = (118, 150, 86)
HIGHLIGHT = (247, 247, 105)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)

# Message queue for communication between threads
speech_queue = queue.Queue()
status_message = "Press SPACE to speak a move"
listening = False
recognized_text = ""
pending_move = None
confirming_move = False
audio_level = 0
# Add this to your global variables section (somewhere near the top with other global definitions)
piece_map = {
    'pawn': '',    # Pawns have no symbol in algebraic notation
    'knight': 'N',
    'bishop': 'B',
    'rook': 'R',
    'queen': 'Q',
    'king': 'K'
}
# Debug mode
DEBUG = True
# Add these to your global variables
MAX_LISTEN_TIME = 5.0  # seconds
SILENCE_THRESHOLD = 100  # Adjust based on testing
SILENCE_DURATION = 1.0  # seconds

listen_start_time = 0
last_sound_time = 0


# Function to draw the chessboard
def draw_board(last_move=None):
    square_size = WIDTH // 8
    for row in range(8):
        for col in range(8):
            color = WHITE if (row + col) % 2 == 0 else GREEN
            if last_move:
                from_file, from_rank = chess.square_file(last_move.from_square), chess.square_rank(last_move.from_square)
                to_file, to_rank = chess.square_file(last_move.to_square), chess.square_rank(last_move.to_square)
                if (col == from_file and 7-row == from_rank) or (col == to_file and 7-row == to_rank):
                    color = HIGHLIGHT
            pygame.draw.rect(screen, color, pygame.Rect(col * square_size, row * square_size, square_size, square_size))
    
    # Draw coordinate labels
    font = pygame.font.Font(None, 20)
    for i in range(8):
        file_label = font.render(chr(97 + i).upper(), True, BLACK if i % 2 == 1 else WHITE)
        screen.blit(file_label, (i * square_size + 5, HEIGHT - 85))
        rank_label = font.render(str(8 - i), True, BLACK if i % 2 == 0 else WHITE)
        screen.blit(rank_label, (5, i * square_size + 5))

# Function to draw the chess pieces
def draw_pieces():
    piece_images = {
        'P': 'white-pawn.png', 'N': 'white-knight.png', 'B': 'white-bishop.png',
        'R': 'white-rook.png', 'Q': 'white-queen.png', 'K': 'white-king.png',
        'p': 'black-pawn.png', 'n': 'black-knight.png', 'b': 'black-bishop.png',
        'r': 'black-rook.png', 'q': 'black-queen.png', 'k': 'black-king.png'
    }
    
    square_size = WIDTH // 8
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            try:
                piece_image = pygame.image.load(f'images/{piece_images[piece.symbol()]}')
                piece_image = pygame.transform.scale(piece_image, (square_size, square_size))
                x = chess.square_file(square) * square_size
                y = (7 - chess.square_rank(square)) * square_size
                screen.blit(piece_image, (x, y))
            except FileNotFoundError:
                color = (200, 0, 0) if piece.color else (0, 0, 200)
                x = chess.square_file(square) * square_size
                y = (7 - chess.square_rank(square)) * square_size
                pygame.draw.circle(screen, color, (x + square_size // 2, y + square_size // 2), square_size // 3)
                font = pygame.font.Font(None, 36)
                text = font.render(piece.symbol(), True, WHITE)
                text_rect = text.get_rect(center=(x + square_size // 2, y + square_size // 2))
                screen.blit(text, text_rect)

# Draw move status text
    global status_message, recognized_text, pending_move, confirming_move, audio_level
    
    pygame.draw.rect(screen, WHITE, pygame.Rect(0, HEIGHT - 50, WIDTH, 50))
    pygame.draw.line(screen, BLACK, (0, HEIGHT - 50), (WIDTH, HEIGHT - 50))
    
    font = pygame.font.Font(None, 30)
    
    game_status = "White's turn" if board.turn else "Black's turn"
    if board.is_checkmate():
        winner = "Black" if board.turn else "White"
        game_status = f"Checkmate! {winner} wins!"
    elif board.is_stalemate():
        game_status = "Stalemate!"
    elif board.is_check():
        game_status = "Check!"
    
    text_surface = font.render(game_status, True, BLACK)
    screen.blit(text_surface, (10, HEIGHT - 90))
    
    if recognized_text:
        text_surface = font.render(f"Heard: {recognized_text}", True, BLACK)
        screen.blit(text_surface, (10, HEIGHT - 50))
    
    # In the draw_status function, enhance the listening indicator:
    if listening:
        listening_text = f"Listening... ({int(MAX_LISTEN_TIME - (time.time() - listen_start_time))}s)"
        text_surface = font.render(listening_text, True, RED)
        screen.blit(text_surface, (10, HEIGHT - 25))
        
        # Enhance the audio level visualization
        bar_max_width = 200
        bar_width = int(min(audio_level * 2000, bar_max_width))
        pygame.draw.rect(screen, (0, 200, 0), pygame.Rect(WIDTH - 220, HEIGHT - 25, bar_width, 20))
        pygame.draw.rect(screen, (200, 200, 200), pygame.Rect(WIDTH - 220 + bar_width, HEIGHT - 25, bar_max_width - bar_width, 20), 1)
    elif confirming_move and pending_move:
        if isinstance(pending_move, chess.Move):
            move_text = board.san(pending_move)
        else:
            move_text = pending_move
        confirm_text = f"Confirm move: {move_text}? (Y/N)"
        text_surface = font.render(confirm_text, True, BLUE)
        screen.blit(text_surface, (10, HEIGHT - 25))
    elif status_message:
        text_surface = font.render(status_message, True, BLACK)
        screen.blit(text_surface, (10, HEIGHT - 25))
def draw_status():
    global status_message, recognized_text, pending_move, confirming_move, audio_level, listening
    
    pygame.draw.rect(screen, WHITE, pygame.Rect(0, HEIGHT - 50, WIDTH, 50))
    pygame.draw.line(screen, BLACK, (0, HEIGHT - 50), (WIDTH, HEIGHT - 50))
    
    font = pygame.font.Font(None, 30)
    
    game_status = "White's turn" if board.turn else "Black's turn"
    if board.is_checkmate():
        winner = "Black" if board.turn else "White"
        game_status = f"Checkmate! {winner} wins!"
    elif board.is_stalemate():
        game_status = "Stalemate!"
    elif board.is_check():
        game_status = "Check!"
    
    text_surface = font.render(game_status, True, BLACK)
    screen.blit(text_surface, (10, HEIGHT - 90))
    
    if recognized_text:
        text_surface = font.render(f"Heard: {recognized_text}", True, BLACK)
        screen.blit(text_surface, (10, HEIGHT - 50))
    
    if listening:
        # If we have the listen_start_time in scope, use it for countdown
        try:
            remaining = MAX_LISTEN_TIME - (time.time() - listen_start_time)
            listening_text = f"Listening... ({int(remaining)}s)"
        except:
            listening_text = "Listening for move..."
            
        text_surface = font.render(listening_text, True, RED)
        screen.blit(text_surface, (10, HEIGHT - 25))
        
        # Enhance the audio level visualization
        bar_max_width = 200
        bar_width = int(min(audio_level * 2000, bar_max_width))
        pygame.draw.rect(screen, (0, 200, 0), pygame.Rect(WIDTH - 220, HEIGHT - 25, bar_width, 20))
        pygame.draw.rect(screen, (200, 200, 200), pygame.Rect(WIDTH - 220 + bar_width, HEIGHT - 25, bar_max_width - bar_width, 20), 1)
    elif confirming_move and pending_move:
        if isinstance(pending_move, chess.Move):
            move_text = board.san(pending_move)
        else:
            move_text = pending_move
        confirm_text = f"Confirm move: {move_text}? (Y/N)"
        text_surface = font.render(confirm_text, True, BLUE)
        screen.blit(text_surface, (10, HEIGHT - 25))
    elif status_message:
        text_surface = font.render(status_message, True, BLACK)
        screen.blit(text_surface, (10, HEIGHT - 25))
def filter_repeated_words(text):
    words = text.split()
    filtered_words = []
    
    # Skip repeated common words, especially "the"
    skip_words = ["the", "to", "a", "and"]
    
    for i, word in enumerate(words):
        # Skip if this word is repeated and is in our skip list
        if i > 0 and word.lower() == words[i-1].lower() and word.lower() in skip_words:
            continue
        # Skip if "the" appears too frequently (more than needed)
        if word.lower() == "the" and i > 1 and "the" in [w.lower() for w in words[i-2:i]]:
            continue
        filtered_words.append(word)
    
    return " ".join(filtered_words)
def voice_listener_thread(model):
    global status_message, listening, audio_level
    
    if model is None:
        print("No speech model available")
        return
    
    p = pyaudio.PyAudio()
    
    try:
        stream = p.open(format=pyaudio.paInt16, 
                        channels=1, 
                        rate=16000, 
                        input=True, 
                        frames_per_buffer=4000)
        stream.start_stream()
        
        rec = vosk.KaldiRecognizer(model, 16000)
        rec.SetWords(True)
        
        print("Voice recognition system is ready")
        
        # Initialize timing variables inside this function
        listen_start_time = 0
        last_sound_time = 0
        
        while True:
            if listening:
                current_time = time.time()
                
                # Start timer when listening begins
                if listen_start_time == 0:
                    listen_start_time = current_time
                    last_sound_time = current_time  # Also initialize last_sound_time
                
                # Check for timeout
                if current_time - listen_start_time > MAX_LISTEN_TIME:
                    print("Listening timeout reached")
                    speech_queue.put("[Timeout - no clear command detected]")
                    listening = False
                    listen_start_time = 0
                    continue
                
                data = stream.read(2000, exception_on_overflow=False)
                audio_array = np.frombuffer(data, dtype=np.int16)
                audio_level = np.abs(audio_array).mean() / 10000.0
                
                # Sound detection logic
                if audio_level > SILENCE_THRESHOLD / 10000.0:
                    last_sound_time = current_time
                elif last_sound_time > 0 and current_time - last_sound_time > SILENCE_DURATION:
                    # If silence for SILENCE_DURATION seconds after speech was detected
                    print("Silence detected, finalizing recognition")
                    result = json.loads(rec.FinalResult())
                    if "text" in result and result["text"]:
                        raw_text = result["text"]
                        try:
                            # First filter out repetitions
                            filtered_text = filter_repeated_words(raw_text)
                            # Then process as usual
                            processed_text = preprocess_speech_input(filtered_text)
                            if DEBUG:
                                print(f"Raw recognition: '{raw_text}'")
                                print(f"After filtering repetitions: '{filtered_text}'")
                                print(f"After preprocessing: '{processed_text}'")
                            speech_queue.put(processed_text)
                        except Exception as e:
                            print(f"Error processing text '{raw_text}': {e}")
                            speech_queue.put(raw_text)
                    listening = False
                    listen_start_time = 0
                    last_sound_time = 0
                    continue
                
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    if "text" in result and result["text"]:
                        raw_text = result["text"]
                        try:
                            # First filter out repetitions
                            filtered_text = filter_repeated_words(raw_text)
                            # Then process as usual
                            processed_text = preprocess_speech_input(filtered_text)
                            if DEBUG:
                                print(f"Raw recognition: '{raw_text}'")
                                print(f"After filtering repetitions: '{filtered_text}'")
                                print(f"After preprocessing: '{processed_text}'")
                            speech_queue.put(processed_text)
                            listening = False
                            listen_start_time = 0
                        except Exception as e:
                            print(f"Error processing text '{raw_text}': {e}")
                            speech_queue.put(raw_text)
                            listening = False
                            listen_start_time = 0
                else:
                    partial = json.loads(rec.PartialResult())
                    if "partial" in partial and partial["partial"] and len(partial["partial"]) > 3:
                        speech_queue.put(f"Partial: {partial['partial']}")
            else:
                listen_start_time = 0  # Reset timer when not listening
                last_sound_time = 0    # Reset silence timer when not listening
                time.sleep(0.1)
    
    except Exception as e:
        print(f"Error in voice listener thread: {e}")
    finally:
        if 'stream' in locals():
            stream.stop_stream()
            stream.close()
        p.terminate()
# Function to set up Vosk
def setup_vosk():
    model_path = r"C:\Users\sabha\OneDrive\Desktop\idea_sprint\vosk-model-en-us-0.22\vosk-model-en-us-0.22"
    
    if not os.path.isdir(model_path):
        print(f"Error: Model directory not found at {model_path}")
        print("Please download the Vosk model from https://alphacephei.com/vosk/models")
        print("Extract 'vosk-model-small-en-us-0.15' to the specified path.")
        return None
    
    try:
        print(f"Loading Vosk model from: {model_path}")
        model = vosk.Model(model_path)
        return model
    except Exception as e:
        print(f"Error loading Vosk model: {e}")
        return None


# Preprocess speech input for accent handling

# Parse voice command into a chess move
# Improved preprocess_speech_input function with better letter and number recognition

def preprocess_speech_input(text):
    if DEBUG:
        print(f"Pre-processing raw input: '{text}'")
    
    # Define a comprehensive number mapping dictionary
    letter_map = {
        # A variations
        'ay': 'a', 'hey': 'a', 'they': 'a', 'ai': 'a', 'aa': 'a', 'ae': 'a', 'yea': 'a', 'yeah': 'a', 
        'at': 'a', 'aye': 'a', 'eh': 'a', 'day': 'a','yay':'a',
        'en': 'n', 'an': 'n', 'in': 'n', 'end': 'n', 'and': 'n', 'yen': 'n', 'hen': 'n', 'ten': 'n',
'are': 'r', 'our': 'r', 'or': 'r', 'arr': 'r', 'air': 'r', 'ear': 'r', 'er': 'r', 'ar': 'r',
'queue': 'q', 'cu': 'q', 'que': 'q', 'cue': 'q', 'kyu': 'q', 'kew': 'q', 'kyou': 'q', 'que': 'q',
'kay': 'k', 'ca': 'k', 'ka': 'k', 'key': 'k', 'ck': 'k', 'ck': 'k', 'kei': 'k', 'kae': 'k',
        
        # B variations
        'be': 'b', 'bee': 'b', 'me': 'b', 'pee': 'b', 'pe': 'b', 'bi': 'b', 'by': 'b', 'boy': 'b', 'bie': 'b',
        
        # C variations
        'see': 'c', 'sea': 'c', 'cie': 'c', 'she': 'c', 'ci': 'c', 'si': 'c', 'say': 'c', 'cee': 'c',
        
        # D variations
        'dee': 'd', 'de': 'd', 'the': 'd', 'di': 'd', 'dey': 'd', 'day': 'd', 'die': 'd',
        
        # E variations
        'ee': 'e', 'ie': 'e', 'ye': 'e', 'ea': 'e', 'yi': 'e', 'eh': 'e', 'eat': 'e', 'eve': 'e',
        
        # F variations
        'ef': 'f', 'ff': 'f', 'if': 'f', 'aff': 'f', 'eff': 'f', 'afro': 'f', 'foe': 'f','yes':'f',
        
        # G variations
        'jee': 'g', 'gee': 'g', 'ji': 'g', 'je': 'g', 'gi': 'g', 'ge': 'g', 'gay': 'g', 'guy': 'g',
        
        # H variations
        'aitch': 'h', 'age': 'h', 'etch': 'h', 'eh': 'h', 'ach': 'h', 'speech': 'h', 'age': 'h', 'itch': 'h'
    }
    number_map = {
        # 1 variations - augmented list
        'one': '1', 'van': '1', 'von': '1', 'won': '1', 'fun': '1', 'on': '1', 'run': '1', 'wine': '1', 'wan': '1',
        'wand': '1', 'want': '1', 'john': '1', 'juan': '1', 'hand': '1', 'an': '1', 'hun': '1', 'done': '1',
        'none': '1', 'gone': '1', 'some': '1', 'son': '1', 'sun': '1',
        
        # 2 variations - augmented list
        'two': '2', 'to': '2', 'too': '2', 'do': '2', 'tu': '2', 'true': '2', 'tru': '2', 'due': '2', 'tools': '2',
        'toe': '2', 'new': '2', 'blue': '2', 'who': '2', 'crew': '2', 'through': '2', 'tour': '2', 'dual': '2',
        'duel': '2', 'cool': '2', 'tune': '2', 'dew': '2', 'shoe': '2', 'chew': '2', 'tell': '2',
        
        # 3 variations - augmented list
        'three': '3', 'tree': '3', 'free': '3', 'sri': '3', 'pre': '3', 'flee': '3', 'the three': '3',
        'thirty': '3', 'string': '3', 'tricky': '3', 'cream': '3', 'tee': '3', 'real': '3', 'plea': '3',
        'treat': '3', 'thread': '3', 'trend': '3', 'treaty': '3',
        
        # 4 variations - augmented list
        'four': '4', 'for': '4', 'far': '4', 'fore': '4', 'floor': '4', 'door': '4', 'more': '4', 'form': '4',
        'ford': '4', 'fourth': '4', 'foreign': '4', 'bore': '4', 'foe': '4', 'fold': '4', 'fort': '4',
        'forty': '4', 'fall': '4', 'fall': '4', 'foam': '4', 'fork': '4', 'or': '4',
        
        # 5 variations - augmented list
        'five': '5', 'phi': '5', 'hive': '5', 'fife': '5', 'fight': '5', 'file': '5', 'find': '5',
        'fiver': '5', 'fiber': '5', 'fine': '5', 'fan': '5', 'phone': '5', 'knife': '5', 'life': '5',
        'wife': '5', 'faith': '5', 'wifi': '5', 'vibe': '5', 'fifth': '5', 'alive': '5','favor':'5','favorite':'5',
        
        # 6 variations - augmented list
        'six': '6', 'sicks': '6', 'sticks': '6', 'sick': '6', 'sex': '6', 'sicks': '6',
        'sic': '6', 'sax': '6', 'seeks': '6', 'sees': '6', 'sync': '6', 'fix': '6', 'bricks': '6',
        'mix': '6', 'hits': '6', 'chicks': '6', 'styx': '6', 'sixty': '6', 'sake': '6',
        
        # 7 variations - augmented list
        'seven': '7', 'savin': '7', 'heaven': '7', 'evan': '7', 'kevin': '7', 'eleven': '7',
        'several': '7', 'seventy': '7', 'seventh': '7', 'sven': '7', 'steven': '7', 'leaven': '7',
        'devon': '7', 'stefan': '7', 'seven and': '7', 'seven in': '7', 'savvy': '7',
        
        # 8 variations - augmented list
        'eight': '8', 'ate': '8', 'hate': '8', 'late': '8', 'date': '8', 'rate': '8', 'gate': '8',
        'aide': '8', 'ape': '8', 'eighty': '8', 'at': '8', 'hey': '8', 'fate': '8', 'wait': '8',
        'great': '8', 'state': '8', 'trait': '8', 'weight': '8', 'mate': '8', 'bait': '8'
    }
    
    # Convert to lowercase and split into words
    text_lower = text.lower()
    words = text_lower.split()
    result_words = []
    
    # Process each word, with special handling for numbers
    for word in words:
        if word in number_map:
            result_words.append(number_map[word])
        else:
            # Try to match partial words for numbers (more aggressive matching)
            replaced = False
            for sound, number in number_map.items():
                # For shorter words, require more exact matches
                if len(word) <= 3:
                    if word == sound:
                        result_words.append(number)
                        replaced = True
                        if DEBUG:
                            print(f"Number match: '{word}' -> '{number}'")
                        break
                # For longer words, allow partial matching with confidence
                elif len(sound) >= 3 and sound in word and len(word) <= len(sound) + 2:
                    result_words.append(number)
                    replaced = True
                    if DEBUG:
                        print(f"Partial number match: '{word}' -> '{number}'")
                    break
            
            if not replaced:
                result_words.append(word)
    
    processed_text = ' '.join(result_words)
    
    # Apply regex patterns for coordinate detection
    coord_patterns = [
        # Join letter-number combinations (with spaces or without)
        (r'\b([a-h])\s+([1-8])\b', r'\1\2'),
        
        # Handle letter + to + number
        (r'\b([a-h])\s+to\s+([1-8])\b', r'\1\2'),
        
        # Handle already numeric cases
        (r'\b([a-h][1-8])\s+to\s+([a-h][1-8])\b', r'\1 to \2'),
    ]
    
    for pattern, replacement in coord_patterns:
        try:
            processed_text = re.sub(pattern, replacement, processed_text)
        except re.error as e:
            if DEBUG:
                print(f"Regex error: {e}, Pattern: '{pattern}', Replacement: '{replacement}', Text: '{processed_text}'")
    
    # Add enhanced patterns for chess notation
    chess_terms = {
        'night': 'knight', 'knights': 'knight', 'knife': 'knight', 'knives': 'knight',
        'pollen': 'pawn', 'porn': 'pawn', 'pond': 'pawn', 'bond': 'pawn',
        'shop': 'bishop', 'fish': 'bishop', 'dish': 'bishop',
        'brook': 'rook', 'roh': 'rook', 'rogue': 'rook', 'look': 'rook', 'took': 'rook',
        'clean': 'queen', 'cream': 'queen', 'screen': 'queen',
        'ring': 'king', 'ping': 'king',
        'cattle': 'castle', 'castle': 'castle', 'cassell': 'castle', 
        'king side': 'kingside', 'queenside': 'queenside', 'queen side': 'queenside'
    }
    
    for wrong, right in chess_terms.items():
        processed_text = re.sub(r'\b' + wrong + r'\b', right, processed_text)
    
    if DEBUG:
        print(f"After preprocessing: '{processed_text}'")
    
    return processed_text
# Enhanced parse_command function with improved move detection
# Enhance the parse_command function to recognize standard chess notation
# Improved normalize_text function with better number handling
# Enhanced parse_command function with improved piece recognition
def parse_command(command):
    global status_message
    
    if command.startswith("Partial:"):
        return None
    
    normalized = normalize_text(command)
    
    if DEBUG:
        coords = re.findall(r'[a-h][1-8]', normalized)
        if coords:
            print(f"Found chess coordinates in normalized text: {coords}")
    
    # --- 1. Check for castling first ---
    if "castle" in normalized:
        if "kingside" in normalized or "king side" in normalized or "short" in normalized or "00" in normalized:
            for move in board.legal_moves:
                if board.is_kingside_castling(move):
                    if DEBUG:
                        print("Kingside castling detected")
                    return move
        elif "queenside" in normalized or "queen side" in normalized or "long" in normalized or "000" in normalized:
            for move in board.legal_moves:
                if board.is_queenside_castling(move):
                    if DEBUG:
                        print("Queenside castling detected")
                    return move
        else:
            # Default to kingside if unclear
            for move in board.legal_moves:
                if board.is_kingside_castling(move):
                    if DEBUG:
                        print("Defaulted to kingside castling")
                    return move
    
    # --- 2. Check for explicit piece mentions ---
    # This new section looks for piece mentions like "knight", "bishop", etc.
    piece_types = {
        'knight': chess.KNIGHT,
        'bishop': chess.BISHOP,
        'rook': chess.ROOK,
        'queen': chess.QUEEN,
        'king': chess.KING,
        'n': chess.KNIGHT,  # Also handle abbreviations
        'b': chess.BISHOP,
        'r': chess.ROOK,
        'q': chess.QUEEN,
        'k': chess.KING
    }
    
    for piece_name, piece_type in piece_types.items():
        if piece_name in normalized:
            # Look for a destination coordinate
            coords = re.findall(r'[a-h][1-8]', normalized)
            if coords:
                dest = coords[-1]  # Use the last coordinate as destination
                for move in board.legal_moves:
                    if (chess.square_name(move.to_square) == dest and 
                        board.piece_at(move.from_square) and 
                        board.piece_at(move.from_square).piece_type == piece_type):
                        if DEBUG:
                            print(f"{piece_name.title()} move detected to {dest}")
                        return move
            break  # If we found a piece mention but no valid move, don't continue to pawn moves
    
    # --- 3. Detect knight moves like "n f3" (this is now redundant but kept for safety) ---
    knight_pattern = re.search(r'\bn\s*([a-h][1-8])\b', normalized)
    if knight_pattern:
        dest = knight_pattern.group(1)
        for move in board.legal_moves:
            if (chess.square_name(move.to_square) == dest and 
                board.piece_at(move.from_square) and 
                board.piece_at(move.from_square).piece_type == chess.KNIGHT):
                if DEBUG:
                    print(f"Knight move detected: N{dest}")
                return move

    # --- 4. Try full SAN matching (piece moves and captures) ---
    san_pattern = re.search(r'([NBRQK])?([a-h][1-8])', normalized)
    if san_pattern:
        piece_letter, destination = san_pattern.groups()
        if destination:
            for move in board.legal_moves:
                move_san = board.san(move)
                stripped_san = move_san.replace("x", "").replace("+", "").replace("#", "").lower()
                
                # Build what user probably meant
                user_san_guess = ''
                if piece_letter:
                    user_san_guess += piece_letter.lower()
                user_san_guess += destination.lower()

                if user_san_guess == stripped_san:
                    if DEBUG:
                        print(f"Matched SAN: User said '{user_san_guess}', matched '{move_san}'")
                    return move

    # --- 5. Check for coordinate pair "e2 to e4" or "e2e4" ---
    coord_pair = re.search(r'([a-h][1-8])\s*to\s*([a-h][1-8])', normalized)
    if coord_pair:
        from_sq, to_sq = coord_pair.groups()
        move_uci = f"{from_sq}{to_sq}"
        try:
            move = chess.Move.from_uci(move_uci)
            if move in board.legal_moves:
                if DEBUG:
                    print(f"Move by coordinates: {from_sq} to {to_sq}")
                return move
        except ValueError:
            pass

    # --- 6. Single square move (pawn usually) ---
    # Only process this if no piece was explicitly mentioned above
    if not any(piece in normalized for piece in piece_types.keys()):
        single_square = re.search(r'\b([a-h][1-8])\b', normalized)
        if single_square:
            dest = single_square.group(1)
            possible_moves = []
            for move in board.legal_moves:
                if chess.square_name(move.to_square) == dest:
                    possible_moves.append(move)

            if possible_moves:
                # Prefer pawn moves if available
                for move in possible_moves:
                    if board.piece_at(move.from_square) and board.piece_at(move.from_square).piece_type == chess.PAWN:
                        if DEBUG:
                            print(f"Single square pawn move to {dest}")
                        return move
                # Else just pick the first matching move
                if DEBUG:
                    print(f"Single square move to {dest} (non-pawn)")
                return possible_moves[0]

    # --- 7. Fallback ---
    if DEBUG:
        print(f"Couldn't parse command into a valid chess move: {command}")
        print(f"Normalized command was: {normalized}")
        print("Legal moves available:")
        for move in board.legal_moves:
            print(f" - {board.san(move)}")
    
    status_message = "Could not understand the move. Try again."
    return None
def normalize_text(text):
    replacements = {
        'eh': 'a', 'ae': 'a', 'ay': 'a', 'ey': 'a', 'ei': 'a','yeah':'a','yay':'a','ye':'a',
        'bee': 'b', 'be': 'b', 'bi': 'b', 'by': 'b', 'pee': 'b', 'pe': 'b',
        'see': 'c', 'sea': 'c', 'si': 'c', 'cee': 'c', 
        'dee': 'd', 'dey': 'd', 'di': 'd', 'the': 'd',
        'ee': 'e', 'ie': 'e', 'ea': 'e', 'yi': 'e', 'ii': 'e',
        'ef': 'f', 'aff': 'f', 'eaf': 'f', 'eff': 'f', 'afe': 'f','yes':'f',
        'gee': 'g', 'ji': 'g', 'jee': 'g', 'gi': 'g',
         'aitch': 'h', 'etch': 'h', 'age': 'h', 'ach': 'h', 'each': 'h','hedge':'h','hetch':'h','heich':'h',
        'a': 'a', 'b': 'b', 'c': 'c','seems':'c', 'd': 'd', 'e': 'e', 'f': 'f', 'g': 'g', 'h': 'h',
        'en': 'n', 'an': 'n', 'in': 'n', 'end': 'n', 'and': 'n', 'yen': 'n','then':'n','jan':'n','jen':'n',
'are': 'r', 'our': 'r', 'or': 'r', 'arr': 'r', 'air': 'r',
'queue': 'q', 'cu': 'q', 'que': 'q', 'cue': 'q', 'kyu': 'q','huh':'q','you':'q',
'kay': 'k', 'ca': 'k', 'ka': 'k', 'key': 'k', 'cay': 'k',
        
        # Enhanced number recognition
        'one': '1', 'van': '1', 'von': '1', 'won': '1', 'fun': '1', 'on': '1', 'run': '1', 'wine': '1', 'wan': '1',
        'two': '2', 'to': '2', 'too': '2', 'do': '2', 'tu': '2', 'true': '2', 'tru': '2', 'due': '2', 'tools': '2',
        'three': '3', 'tree': '3','they':'3', 'free': '3', 'sri': '3', 'pre': '3', 'flee': '3', 'the three': '3',
        'four': '4','thought':'4', 'for': '4', 'far': '4', 'fore': '4', 'floor': '4', 'door': '4', 'more': '4', 'form': '4',
        'five': '5', 'phi': '5', 'hive': '5', 'fife': '5', 'fight': '5', 'file': '5', 'find': '5','faill':'5','fame':'5',
        'six': '6', 'sicks': '6', 'sticks': '6', 'sick': '6', 'sex': '6',
        'seven': '7', 'savin': '7', 'heaven': '7', 'evan': '7', 'kevin': '7', 'eleven': '7',
        'eight': '8', 'ate': '8', 'hate': '8', 'late': '8', 'date': '8', 'rate': '8', 'gate': '8','aight':'8',
        
        # Chess piece mappings (unchanged)
        'pawn': 'pawn', 'porn': 'pawn', 'pond': 'pawn', 'bond': 'pawn',
        'night': 'knight', 'knights': 'knight', 'knife': 'knight', 'knives': 'knight',
        'bishop': 'bishop', 'shop': 'bishop', 'fish': 'bishop', 'dish': 'bishop',
        'rook': 'rook', 'book': 'rook', 'brooke': 'rook', 'brook': 'rook', 'took': 'rook',
        'queen': 'queen', 'clean': 'queen', 'cream': 'queen', 'screen': 'queen',
        'king': 'king', 'ring': 'king', 'ping': 'king',
        'capture': 'capture', 'captures': 'capture', 'takes': 'capture', 'take': 'capture',
        'move': 'move', 'moves': 'move', 'moving': 'move',
        'castle': 'castle', 'castles': 'castle', 'castling': 'castle', 'cassell': 'castle',
        'castleside': 'castle kingside', 'castle side': 'castle kingside',
        'kingside': 'kingside', 'king side': 'kingside', "king's side": 'kingside',
        'queenside': 'queenside', 'queen side': 'queenside', "queen's side": 'queenside',
        'short': 'kingside', 'short castle': 'castle kingside',
        'long': 'queenside', 'long castle': 'castle queenside',
        'promote': 'promote', 'promotion': 'promote',
        'check': 'check',
        
        # Special case coordinate mappings
        'e2e4': 'e2 to e4',
        'e two e four': 'e2 to e4',
        'e 2 e 4': 'e2 to e4',
        'e two to e four': 'e2 to e4',
    }
    
    normalized = text.lower()
    if DEBUG:
        print(f"Original text: '{text}'")
        print(f"Lowercase text: '{normalized}'")
    
    for wrong, right in replacements.items():
        normalized = re.sub(r'\b' + wrong + r'\b', right, normalized)
    
    isolated_letters = {
        'ay': 'a', 'bee': 'b', 'see': 'c', 'dee': 'd', 
        'ee': 'e', 'ef': 'f', 'gee': 'g', 'aitch': 'h'
    }
    
    words = normalized.split()
    for i, word in enumerate(words):
        if len(word) <= 3:
            for sound, letter in isolated_letters.items():
                if sound == word:
                    words[i] = letter
                    if DEBUG:
                        print(f"Replaced isolated '{word}' with '{letter}'")
    
    normalized = ' '.join(words)
    
    # Enhanced coordinate patterns
    # First join letter-number pairs like "e 4" -> "e4"
    coord_pattern = r'([a-h])\s*[-\s]*([1-8])'
    normalized = re.sub(coord_pattern, r'\1\2', normalized)
    
    # Extended accent patterns
    indian_accent_patterns = {
        # e row
        r'e do': 'e2', r'e to': 'e2', r'e too': 'e2', r'e two': 'e2', r'e tu': 'e2',
        r'e tree': 'e3', r'e three': 'e3', r'e free': 'e3',
        r'e for': 'e4', r'e four': 'e4', r'e far': 'e4', r'e floor': 'e4', 
        r'e five': 'e5', r'e phi': 'e5',
        r'e six': 'e6', r'e sicks': 'e6',
        r'e seven': 'e7', r'e savin': 'e7',
        r'e eight': 'e8', r'e ate': 'e8',
        
        # a row
        r'a do': 'a2', r'a to': 'a2', r'a too': 'a2', r'a two': 'a2', r'a tu': 'a2',
        r'a tree': 'a3', r'a three': 'a3', r'a free': 'a3',
        r'a for': 'a4', r'a four': 'a4', r'a far': 'a4',
        r'a five': 'a5', r'a phi': 'a5',
        r'a six': 'a6', r'a sicks': 'a6',
        r'a seven': 'a7', r'a savin': 'a7',
        r'a eight': 'a8', r'a ate': 'a8',
        
        # b row
        r'be do': 'b2', r'b do': 'b2', r'b to': 'b2', r'b too': 'b2', r'b two': 'b2',
        r'be tree': 'b3', r'b tree': 'b3', r'b three': 'b3', r'b free': 'b3',
        r'be for': 'b4', r'b for': 'b4', r'b four': 'b4', r'b far': 'b4',
        r'be five': 'b5', r'b five': 'b5', r'b phi': 'b5',
        r'be six': 'b6', r'b six': 'b6', r'b sicks': 'b6',
        r'be seven': 'b7', r'b seven': 'b7', r'b savin': 'b7',
        r'be eight': 'b8', r'b eight': 'b8', r'b ate': 'b8',
        
        # c row 
        r'see do': 'c2', r'c do': 'c2', r'c to': 'c2', r'c too': 'c2', r'c two': 'c2',
        r'see tree': 'c3', r'c tree': 'c3', r'c three': 'c3', r'c free': 'c3',
        r'see for': 'c4', r'c for': 'c4', r'c four': 'c4', r'c far': 'c4',
        r'see five': 'c5', r'c five': 'c5', r'c phi': 'c5',
        r'see six': 'c6', r'c six': 'c6', r'c sicks': 'c6',
        r'see seven': 'c7', r'c seven': 'c7', r'c savin': 'c7',
        r'see eight': 'c8', r'c eight': 'c8', r'c ate': 'c8',
        
        # d row
        r'de do': 'd2', r'd do': 'd2', r'd to': 'd2', r'd too': 'd2', r'd two': 'd2',
        r'de tree': 'd3', r'd tree': 'd3', r'd three': 'd3', r'd free': 'd3',
        r'de for': 'd4', r'd for': 'd4', r'd four': 'd4', r'd far': 'd4',
        r'de five': 'd5', r'd five': 'd5', r'd phi': 'd5',
        r'de six': 'd6', r'd six': 'd6', r'd sicks': 'd6',
        r'de seven': 'd7', r'd seven': 'd7', r'd savin': 'd7',
        r'de eight': 'd8', r'd eight': 'd8', r'd ate': 'd8',
        
        # g row
        r'ge do': 'g2', r'g do': 'g2', r'g to': 'g2', r'g too': 'g2', r'g two': 'g2',
        r'ge tree': 'g3', r'g tree': 'g3', r'g three': 'g3', r'g free': 'g3',
        r'ge for': 'g4', r'g for': 'g4', r'g four': 'g4', r'g far': 'g4',
        r'ge five': 'g5', r'g five': 'g5', r'g phi': 'g5',
        r'ge six': 'g6', r'g six': 'g6', r'g sicks': 'g6',
        r'ge seven': 'g7', r'g seven': 'g7', r'g savin': 'g7',
        r'ge eight': 'g8', r'g eight': 'g8', r'g ate': 'g8',
        
        # h row
        r'h do': 'h2', r'h to': 'h2', r'h too': 'h2', r'h two': 'h2',
        r'h tree': 'h3', r'h three': 'h3', r'h free': 'h3',
        r'h for': 'h4', r'h four': 'h4', r'h far': 'h4',
        r'h five': 'h5', r'h phi': 'h5',
        r'h six': 'h6', r'h sicks': 'h6',
        r'h seven': 'h7', r'h savin': 'h7',
        r'h eight': 'h8', r'h ate': 'h8',
        
        # f row
        r'f do': 'f2', r'f to': 'f2', r'f too': 'f2', r'f two': 'f2',
        r'f tree': 'f3', r'f three': 'f3', r'f free': 'f3',
        r'f for': 'f4', r'f four': 'f4', r'f far': 'f4',
        r'f five': 'f5', r'f phi': 'f5',
        r'f six': 'f6', r'f sicks': 'f6',
        r'f seven': 'f7', r'f savin': 'f7',
        r'f eight': 'f8', r'f ate': 'f8',
    }
    
    # Apply all the accent-specific patterns
    for pattern, replacement in indian_accent_patterns.items():
        normalized = normalized.replace(pattern, replacement)
    
    # Final pass to join any remaining coordinates like "e 4" -> "e4"
    normalized = re.sub(r'([a-h])\s+([1-8])', r'\1\2', normalized)
    
    
    if DEBUG:
        print(f"Normalized: '{text}' -> '{normalized}'")
        print(f"Words detected: {normalized.split()}")
    
    return normalized

# Improved function to extract coordinate pairs from text
def extract_coordinate_pairs(text):
    """Extract potential coordinate pairs from text with enhanced detection"""
    coord_pairs = []
    
    # Detect full coordinates (e.g., "e2e4", "e2 to e4")
    full_coords = re.findall(r'([a-h][1-8])[- ]?(?:to)?[- ]?([a-h][1-8])', text)
    if full_coords:
        coord_pairs.extend(full_coords)
        if DEBUG:
            print(f"Found full coordinate pairs: {full_coords}")
    
    # Detect separate coordinates that might form a pair
    coords = re.findall(r'[a-h][1-8]', text)
    if len(coords) >= 2:
        # Take first two distinct coordinates as a potential move
        if coords[0] != coords[1]:
            coord_pairs.append((coords[0], coords[1]))
            if DEBUG:
                print(f"Found separate coordinates that may form a pair: {coords[0]}, {coords[1]}")
    
    return coord_pairs
# Extract chess coordinates from text
def extract_chess_coordinates(text):
    files = re.findall(r'\b([a-h])\b', text)
    ranks = re.findall(r'\b([1-8])\b', text)
    
    if DEBUG:
        if files:
            print(f"Found potential files: {files}")
        if ranks:
            print(f"Found potential ranks: {ranks}")
    
    if len(files) == 1 and len(ranks) == 1:
        coord = files[0] + ranks[0]
        if DEBUG:
            print(f"Constructed coordinate from individual characters: {coord}")
        return coord
    
    return None

# Make a move on the chessboard
def make_move(move):
    global status_message
    
    if isinstance(move, str):
        try:
            move_obj = board.parse_san(move)
            board.push(move_obj)
            status_message = f'Move executed: {move}'
            print(status_message)
            return move_obj
        except ValueError:
            status_message = f'Invalid move: {move}'
            print(status_message)
            return None
    elif isinstance(move, chess.Move):
        try:
            san_move = board.san(move)
            board.push(move)
            status_message = f'Move executed: {san_move}'
            print(status_message)
            return move
        except ValueError:
            status_message = "Invalid move"
            print(status_message)
            return None
    
    status_message = "Invalid move format"
    return None

# Show available legal moves
def show_legal_moves():
    moves = [board.san(move) for move in board.legal_moves]
    print("Legal moves:", moves)
    return moves

# Draw help overlay
def draw_help_overlay():
    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.set_alpha(230)
    overlay.fill(WHITE)
    screen.blit(overlay, (0, 0))
    
    font = pygame.font.Font(None, 30)
    title_font = pygame.font.Font(None, 40)
    
    title = title_font.render("Voice Command Help", True, BLACK)
    screen.blit(title, (WIDTH//2 - title.get_width()//2, 20))
    
    commands = [
        "Press SPACE to start listening",
        "Press H to show/hide this help",
        "Press ESC to quit",
        "Press Y to confirm a move",
        "Press N to reject a move",
        "",
        "Voice Command Examples:",
        "- \"e4\" (for pawn to e4)",
        "- \"Knight to f3\"",
        "- \"e2 to e4\"",
        "- \"castle\" or \"castle kingside\"",
        "- \"queen side castle\"",
        "",
        "Tips:",
        "- Speak clearly and at a normal pace",
        "- Speak loudly enough (watch the green bar)",
        "- Use standard chess notation when possible",
        "- If recognition fails, try rephrasing"
    ]
    
    y = 80
    for cmd in commands:
        if cmd == "":
            y += 20
            continue
        text = font.render(cmd, True, BLACK)
        screen.blit(text, (WIDTH//2 - text.get_width()//2, y))
        y += 35
    
    pygame.draw.rect(screen, (200, 200, 200), pygame.Rect(WIDTH - 100, HEIGHT - 50, 90, 40))
    close_text = font.render("Close", True, BLACK)
    screen.blit(close_text, (WIDTH - 55 - close_text.get_width()//2, HEIGHT - 30 - close_text.get_height()//2))

# Main game loop
def main():
    global status_message, listening, recognized_text, pending_move, confirming_move
    
    model = setup_vosk()
    if not model:
        print("Failed to set up speech recognition. Exiting.")
        pygame.quit()
        sys.exit(1)
    
    speech_thread = threading.Thread(target=voice_listener_thread, args=(model,), daemon=True)
    speech_thread.start()
    
    last_move = None
    clock = pygame.time.Clock()
    running = True
    show_help = True
    
    print("Current board state:")
    print(board)
    legal_moves = show_legal_moves()
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    if not listening and not confirming_move:
                        listening = True
                        recognized_text = ""
                        status_message = "Listening for move..."
                        print("Listening for command...")
                elif event.key == pygame.K_h:
                    show_help = not show_help
                elif event.key == pygame.K_y and confirming_move:
                    if pending_move:
                        last_move = make_move(pending_move)
                        pending_move = None
                        confirming_move = False
                        legal_moves = show_legal_moves()
                elif event.key == pygame.K_n and confirming_move:
                    pending_move = None
                    confirming_move = False
                    status_message = "Move rejected. Press SPACE to try again."
            if event.type == pygame.MOUSEBUTTONDOWN and show_help:
                if WIDTH - 100 <= event.pos[0] <= WIDTH - 10 and HEIGHT - 50 <= event.pos[1] <= HEIGHT - 10:
                    show_help = False
        
        try:
            if not speech_queue.empty():
                command = speech_queue.get_nowait()
                print(f"Recognized: {command}")
                recognized_text = command
                if not command.startswith("Partial:"):
                    move = parse_command(command)
                    if move:
                        pending_move = move
                        confirming_move = True
                        status_message = "Confirm this move? (Y/N)"
        except queue.Empty:
            pass
        
        screen.fill(WHITE)
        draw_board(last_move)
        draw_pieces()
        draw_status()
        if show_help:
            draw_help_overlay()
        
        pygame.display.flip()
        clock.tick(30)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()