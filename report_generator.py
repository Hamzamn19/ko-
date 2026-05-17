import json
from datetime import datetime, timezone
from typing import List, Dict, Any

def get_performance_comment(percentage: float) -> str:
    if percentage >= 90: return "Mükemmel bir başarı. Konuya tam hakimiyet gözlemleniyor."
    if percentage >= 75: return "Oldukça iyi bir performans. Bazı küçük eksikler olabilir."
    if percentage >= 60: return "Kabul edilebilir seviyede. Temel kavramlar anlaşılmış."
    if percentage >= 40: return "Geliştirilmesi gereken alanlar var. Daha fazla pratik önerilir."
    return "Kritik seviyede. Konu tekrarı ve yoğun çalışma gerektiriyor."

def get_severity(percentage: float) -> str:
    if percentage < 40: return "kritik"
    if percentage < 60: return "geliştirilmeli"
    return "kabul edilebilir"

def convert_report_to_html(data: dict, report: dict, quiz: list) -> str:
    """Generates a full, valid HTML document for professional email delivery."""
    student_name = data.get("student", {}).get("name", "Öğrenci")
    
    strong_html = "".join([f"<li style='margin-bottom: 8px;'><b style='color: #059669;'>{t['tag']}</b> (%{t['percentage']}): {t['comment']}</li>" for t in report.get("strong_topics", [])])
    weak_html = "".join([f"<li style='margin-bottom: 8px;'><b style='color: #dc2626;'>{t['tag']}</b> (%{t['percentage']}) - <i style='color: #64748b;'>{t['severity']}</i>: {t['comment']}</li>" for t in report.get("weak_topics", [])])
    recs_html = "".join([f"<li style='margin-bottom: 8px;'>{r}</li>" for r in report.get("recommendations", [])])
    
    quiz_html = ""
    if quiz:
        quiz_items = []
        for q in quiz:
            options = "".join([f"<li style='margin-bottom: 4px;'>{k}: {v}</li>" for k, v in q['options'].items()])
            quiz_items.append(f"""
                <div style="margin-bottom: 15px; padding: 15px; border: 1px solid #e2e8f0; border-radius: 8px; background-color: #fdfdfd;">
                    <p style="margin: 0 0 10px 0; font-weight: bold; color: #1e293b;">Soru {q['question_number']}: {q['question_text']}</p>
                    <ul style="margin: 0 0 10px 0; padding-left: 20px; color: #475569; font-size: 14px;">{options}</ul>
                    <p style="margin: 0; color: #059669; font-size: 14px;"><b>Doğru Cevap: {q['correct_answer']}</b></p>
                    <p style="margin: 5px 0 0 0; font-size: 13px; color: #64748b; font-style: italic;">Açıklama: {q['explanation']}</p>
                </div>
            """)
        quiz_html = f"<h3 style='color: #4f46e5; margin-top: 30px; margin-bottom: 15px; border-left: 4px solid #4f46e5; padding-left: 10px;'>📝 Takviye Testi</h3>" + "".join(quiz_items)

    html = f"""<!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f8fafc; padding: 20px 0;">
            <tr>
                <td align="center">
                    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 30px; text-align: left; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                        <h2 style="color: #4f46e5; border-bottom: 2px solid #f1f5f9; padding-bottom: 15px; margin-top: 0; font-size: 24px;">📊 Performans Analiz Raporu</h2>
                        
                        <p style="font-size: 16px; color: #334155;">Sayın <b>{student_name}</b>,</p>
                        <p style="font-size: 15px; color: #475569; line-height: 1.6;">{report.get('general_assessment', '')}</p>
                        
                        <h3 style="color: #059669; margin-top: 25px; margin-bottom: 10px;">💪 Güçlü Yönler</h3>
                        <ul style="padding-left: 20px; color: #475569; font-size: 14px;">{strong_html if strong_html else "<li>Henüz yeterli veri yok.</li>"}</ul>
                        
                        <h3 style="color: #dc2626; margin-top: 25px; margin-bottom: 10px;">📉 Gelişim Alanları</h3>
                        <ul style="padding-left: 20px; color: #475569; font-size: 14px;">{weak_html if weak_html else "<li>Harika! Kritik zayıf yön gözlemlenmedi.</li>"}</ul>
                        
                        <h3 style="color: #1e293b; margin-top: 25px; margin-bottom: 10px;">📈 Trend Analizi</h3>
                        <p style="font-size: 14px; color: #475569; background-color: #f1f5f9; padding: 10px; border-radius: 6px;">{report.get('trend_analysis', '')}</p>
                        
                        <h3 style="color: #4f46e5; margin-top: 25px; margin-bottom: 10px;">💡 Öneriler</h3>
                        <ul style="padding-left: 20px; color: #475569; font-size: 14px;">{recs_html}</ul>
                        
                        {quiz_html}
                        
                        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #f1f5f9; text-align: center;">
                            <p style="font-size: 12px; color: #94a3b8; margin: 0;">
                                Bu rapor <b>Apex Assessment Platform</b> tarafından otomatik olarak oluşturulmuştur.<br>
                                Oluşturulma Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}
                            </p>
                        </div>
                    </div>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return html

def generate_local_student_report(data: dict, include_quiz: bool = True) -> dict:
    student = data.get("student", {})
    avg_pct = data.get("overall_average_percentage", 0)
    tag_perf = data.get("string_tag_performance", {})
    
    # 1. General Assessment
    assessment = f"Öğrencinin genel başarı oranı %{avg_pct}. "
    if avg_pct >= 70:
        assessment += "Genel olarak başarılı bir grafik sergiliyor."
    elif avg_pct >= 50:
        assessment += "Ortalama bir performans gösteriyor, gelişim potansiyeli mevcut."
    else:
        assessment += "Akademik destek ve düzenli tekrar gerektiren bir seviyede."

    # 2. Strong & Weak Topics
    strong_topics = []
    weak_topics = []
    
    sorted_tags = sorted(tag_perf.items(), key=lambda x: x[1]["percentage"], reverse=True)
    
    for tag, perf in sorted_tags:
        pct = perf["percentage"]
        if pct >= 75:
            strong_topics.append({
                "tag": tag,
                "percentage": pct,
                "comment": get_performance_comment(pct)
            })
        elif pct < 60:
            weak_topics.append({
                "tag": tag,
                "percentage": pct,
                "severity": get_severity(pct),
                "comment": get_performance_comment(pct)
            })

    # 3. Recommendations
    recommendations = []
    if not weak_topics:
        recommendations.append("Mevcut başarıyı korumak için düzenli tekrar yapmaya devam edilmeli.")
        recommendations.append("Daha ileri seviye kaynaklardan zorluk derecesi yüksek sorular çözülebilir.")
    else:
        for wt in weak_topics[:3]:
            recommendations.append(f"'{wt['tag']}' konusu üzerine yoğunlaşılmalı ve eksik kalan teorik kısımlar gözden geçirilmeli.")
        recommendations.append("Hatalı çözülen soruların analizine daha fazla vakit ayrılmalı.")

    # 4. Local Quiz (Using questions_bank.json)
    quiz = []
    if include_quiz and weak_topics:
        questions_bank = {}
        try:
            with open("questions_bank.json", "r", encoding="utf-8") as f:
                questions_bank = json.load(f)
        except Exception as e:
            print(f"[Report] Could not load questions_bank.json: {e}")

        import random
        q_count = 0
        for wt in weak_topics[:5]: # Focus on up to 5 weak topics
            tag = wt["tag"]
            # Try to find specific questions for this tag, fall back to "General"
            available_qs = questions_bank.get(tag) or questions_bank.get("General", [])
            
            if available_qs:
                # Pick a random question from available ones
                q_template = random.choice(available_qs)
                q_count += 1
                quiz.append({
                    "question_number": q_count,
                    "target_tag": tag,
                    "difficulty": q_template.get("difficulty", "orta"),
                    "question_text": q_template["question_text"],
                    "options": q_template["options"],
                    "correct_answer": q_template["correct_answer"],
                    "explanation": q_template.get("explanation", f"Bu soru {tag} konusundaki temel eksiklikleri gidermek amacıyla seçilmiştir.")
                })

    report_content = {
        "general_assessment": assessment,
        "strong_topics": strong_topics,
        "weak_topics": weak_topics,
        "trend_analysis": f"Öğrenci toplam {data.get('total_exams', 0)} sınava katılmıştır. Genel trend stabil seyretmektedir.",
        "recommendations": recommendations
    }
    
    html_report = convert_report_to_html(data, report_content, quiz)

    return {
        "report": report_content,
        "quiz": quiz if include_quiz else [],
        "html_report": html_report
    }

def generate_local_class_report(data: dict) -> dict:
    # 1. Distribution
    dist = {"excellent": [], "good": [], "average": [], "weak": [], "critical": []}
    
    all_scores = []
    tag_totals = {} # tag -> {earned, max}

    for s in data.get("students", []):
        pct = s.get("percentage", 0)
        name = s.get("name") or s.get("student_number")
        all_scores.append(pct)
        
        if pct >= 90: dist["excellent"].append(name)
        elif pct >= 75: dist["good"].append(name)
        elif pct >= 50: dist["average"].append(name)
        elif pct >= 25: dist["weak"].append(name)
        else: dist["critical"].append(name)
        
        for score in s.get("scores", []):
            tag = score.get("string_tag")
            if tag:
                if tag not in tag_totals: tag_totals[tag] = {"earned": 0, "max": 0}
                tag_totals[tag]["earned"] += score.get("points_awarded", 0)
                tag_totals[tag]["max"] += score.get("max_points", 10)

    # 2. Topic Analysis
    topic_analysis = []
    for tag, totals in tag_totals.items():
        avg_pct = round((totals["earned"] / totals["max"] * 100), 1) if totals["max"] > 0 else 0
        status = "güçlü" if avg_pct >= 75 else ("orta" if avg_pct >= 50 else "zayıf")
        topic_analysis.append({
            "tag": tag,
            "class_average_percentage": avg_pct,
            "status": status,
            "comment": f"Sınıf geneli bu konuda {status} bir performans sergiliyor."
        })

    # 3. At Risk
    at_risk = []
    for s in data.get("students", []):
        if s.get("percentage", 0) < 50:
            weak_tags = []
            for sc in s.get("scores", []):
                pts = sc.get("points_awarded", 0)
                mx = sc.get("max_points") or 10
                if (pts / mx) < 0.5:
                    weak_tags.append(sc.get("string_tag"))
            
            at_risk.append({
                "student_number": s.get("student_number"),
                "name": s.get("name"),
                "percentage": s.get("percentage"),
                "weak_tags": list(set(filter(None, weak_tags)))
            })

    avg_score = round(sum(all_scores)/len(all_scores), 1) if all_scores else 0

    return {
        "report": {
            "general_assessment": f"Sınıfın genel başarı ortalaması %{avg_score}. Toplam {len(all_scores)} öğrenci değerlendirmeye alınmıştır.",
            "topic_analysis": sorted(topic_analysis, key=lambda x: x["class_average_percentage"], reverse=True),
            "grade_distribution": {k: {"count": len(v), "students": v} for k, v in dist.items()},
            "at_risk_students": at_risk,
            "recommendations": [
                "Zayıf kalınan konularda sınıf içi ek etütler planlanmalı.",
                "Başarı oranı yüksek öğrencilerin akran danışmanlığı yapması teşvik edilebilir.",
                "Sınav sorularının zorluk seviyesi ve konu dağılımı tekrar gözden geçirilmeli."
            ]
        }
    }
